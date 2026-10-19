import csv
import hashlib
import io
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from sqlalchemy import select
from .database import Record, Job, now
from .intelligence import analyze, overview

MAX_POSTS = 5000


def records(db, workspace, kind):
    return list(db.scalars(select(Record).where(Record.workspace_id == workspace, Record.kind == kind).order_by(Record.created_at.desc())))


def serialize(record):
    return {**record.payload, 'id': record.id, 'created_at': record.created_at}


def posts(db, workspace, q='', sentiment='', source='', start='', end=''):
    return [p for r in records(db, workspace, 'post') if (p := serialize(r))
            and q.casefold() in p['text'].casefold()
            and (not sentiment or p['sentiment'] == sentiment)
            and (not source or p['source'] == source)
            and (not start or p.get('published_at', '')[:10] >= start)
            and (not end or p.get('published_at', '')[:10] <= end)]


def audit(db, workspace, actor, action, detail):
    db.add(Record(workspace_id=workspace, kind='audit', payload={'actor': actor, 'action': action, 'detail': detail}))


def add_posts(db, workspace, rows):
    existing = {r.external_id for r in records(db, workspace, 'post')}
    added = duplicates = empty = 0
    for row in rows:
        text = str(row.get('text') or '').strip()
        if not text:
            empty += 1
            continue
        if len(text) > 20000:
            raise ValueError('Posts cannot exceed 20,000 characters.')
        source = str(row.get('source') or 'CSV').strip()[:100]
        date = str(row.get('published_at') or '').strip()
        if date:
            try:
                parsed = datetime.fromisoformat(date.replace('Z', '+00:00'))
                date = (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)).isoformat()
            except ValueError:
                raise ValueError('Dates must use ISO 8601, for example 2026-10-19.')
        identity = hashlib.sha256(json.dumps([text, source, date]).encode()).hexdigest()
        if identity in existing:
            duplicates += 1
            continue
        if len(existing) >= MAX_POSTS:
            raise ValueError('Workspace limit is 5,000 conversations. Create a new workspace for another dataset.')
        existing.add(identity)
        url=str(row.get('url') or '')[:2000]
        parsed_url=urlsplit(url)
        if parsed_url.scheme not in ('http','https') or not parsed_url.hostname or parsed_url.username or parsed_url.password:url=''
        db.add(Record(workspace_id=workspace, kind='post', external_id=identity,
                      payload={'text': text, 'source': source, 'published_at': date, **analyze(text),
                               'url':url, 'remote_id':str(row.get('remote_id') or '')[:200],
                               'assignee': '', 'status': 'open', 'notes': []}))
        added += 1
    db.flush()
    return {'imported': added, 'duplicates': duplicates, 'empty': empty}


def evaluate_monitors(db, workspace):
    all_posts = posts(db, workspace)
    known = {r.external_id for r in records(db, workspace, 'alert')}
    created = 0
    cutoff = (datetime.now(timezone.utc)-timedelta(hours=24)).isoformat()
    current = datetime.now(timezone.utc).isoformat()
    for monitor in records(db, workspace, 'monitor'):
        spec = monitor.payload
        matched = [p for p in all_posts if spec['keyword'].casefold() in p['text'].casefold()
                   and (not spec.get('sentiment') or p['sentiment'] == spec['sentiment'])
                   and cutoff <= (p['published_at'] or p['created_at']) <= current]
        if len(matched) < spec['threshold']:
            continue
        key = hashlib.sha256((monitor.id + ''.join(sorted(p['id'] for p in matched))).encode()).hexdigest()
        if key in known:
            continue
        db.add(Record(workspace_id=workspace, kind='alert', external_id=key,
                      payload={'monitor_id': monitor.id, 'title': spec['name'], 'count': len(matched),
                               'evidence': [p['id'] for p in matched[:20]], 'status': 'open',
                               'detail': f'{len(matched)} matching conversations in the last 24 hours.'}))
        created += 1
    return created


def report(db, workspace, name='Workspace report'):
    data = posts(db, workspace)
    summary = overview(data)
    entry = Record(workspace_id=workspace, kind='report', payload={'name': name, 'summary': summary,
                   'evidence': [{'id': p['id'], 'text': p['text'], 'source': p['source']} for p in data[:10]]})
    db.add(entry)
    db.flush()
    return serialize(entry)


def run_job(factory, job_id):
    """Single-worker durable queue; state and imported data commit together."""
    with factory() as db:
        job = db.get(Job, job_id)
        if not job or job.state != 'pending':
            return
        job.state, job.attempts = 'running', job.attempts + 1
        db.commit()
    try:
        with factory.begin() as db:
            job = db.get(Job, job_id)
            if job.kind == 'import':
                reader = csv.DictReader(io.StringIO(job.payload['csv'].lstrip('\ufeff')), strict=True)
                if not reader.fieldnames or 'text' not in reader.fieldnames:
                    raise ValueError('CSV must contain a text column.')
                result = add_posts(db, job.workspace_id, reader)
                result['alerts'] = evaluate_monitors(db, job.workspace_id)
            elif job.kind == 'report':
                result = {'report_id': report(db, job.workspace_id)['id']}
            elif job.kind == 'bluesky':
                from .connectors import bluesky
                result = add_posts(db, job.workspace_id, bluesky(job.payload['query']))
                result['alerts'] = evaluate_monitors(db, job.workspace_id)
            elif job.kind in ('mastodon','youtube'):
                from .connectors import mastodon, youtube
                connector=mastodon if job.kind=='mastodon' else youtube
                result=add_posts(db,job.workspace_id,connector(job.payload['query']))
                result['alerts']=evaluate_monitors(db,job.workspace_id)
            elif job.kind == 'reanalyze':
                updated = 0
                for record in records(db, job.workspace_id, 'post'):
                    if not record.payload.get('reviewed'):
                        record.payload = {**record.payload, **analyze(record.payload['text'])}
                        updated += 1
                result = {'updated': updated}
            else:
                raise ValueError('Unknown job type.')
            job.state, job.result, job.payload = 'completed', result, {}
            audit(db, job.workspace_id, 'worker', job.kind + '.completed', result)
    except Exception as error:
        logging.getLogger('social_ear.jobs').error('job_failed id=%s error_type=%s', job_id, type(error).__name__)
        with factory.begin() as db:
            job = db.get(Job, job_id)
            job.state = 'failed'
            # Do not persist network exceptions that may contain URLs or credentials.
            message = str(error) if isinstance(error, (ValueError, csv.Error)) else 'Processing failed. Check server logs and retry.'
            job.result = {'error': message[:500]}


def worker(factory, stop):
    # This application intentionally runs one API process and one worker thread.
    with factory.begin() as db:
        for job in db.scalars(select(Job).where(Job.state == 'running')):
            job.state = 'pending'
    while not stop.is_set():
        schedule_due(factory)
        with factory() as db:
            ids = list(db.scalars(select(Job.id).where(Job.state == 'pending').order_by(Job.created_at).limit(4)))
        for identity in ids:
            if stop.is_set():
                return
            run_job(factory, identity)
        stop.wait(1)


def schedule_due(factory):
    with factory.begin() as db:
        schedules = list(db.scalars(select(Record).where(Record.kind == 'schedule')))
        for entry in schedules:
            spec = entry.payload
            if spec['enabled'] and spec['next_run'] <= time.time():
                db.add(Job(workspace_id=entry.workspace_id, kind='report', payload={}))
                entry.payload = {**spec, 'next_run': time.time() + spec['interval_hours']*3600}
