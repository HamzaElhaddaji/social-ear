"""Social Ear authenticated application. Run python -m app."""
import csv
import io
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .database import database, User, Workspace, Membership, Session, Record, Job
from .security import hash_password, verify_password, token_hash, RateLimiter
from .service import records, posts, serialize, audit, evaluate_monitors, worker
from .intelligence import overview, research

ROOT = Path(__file__).resolve().parent.parent


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Credentials(Input):
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(default='Researcher', min_length=1, max_length=80)


class WorkspaceInput(Input):
    name: str = Field(min_length=1, max_length=80)


class MemberInput(Input):
    email: str = Field(max_length=254)
    role: Literal['analyst', 'viewer'] = 'analyst'


class MonitorInput(Input):
    name: str = Field(min_length=1, max_length=80)
    keyword: str = Field(min_length=1, max_length=100)
    threshold: int = Field(default=3, ge=1, le=5000)
    sentiment: Literal['', 'positive', 'negative', 'neutral', 'unclassified'] = ''


class ReviewInput(Input):
    sentiment: Literal['positive', 'negative', 'neutral', 'unclassified']
    status: Literal['open', 'investigating', 'resolved'] = 'open'
    assignee: str = Field(default='', max_length=254)
    note: str = Field(default='', max_length=2000)


class Question(Input):
    question: str = Field(min_length=3, max_length=1000)


class ConnectorInput(Input):
    query: str = Field(min_length=2, max_length=200)


class ScheduleInput(Input):
    interval_hours: int = Field(default=24, ge=1, le=168)
    enabled: bool = True


class CompetitorInput(Input):
    name: str = Field(min_length=1, max_length=80)
    keyword: str = Field(min_length=1, max_length=100)


def create_app(url=None, start_worker=True):
    engine, factory = database(url)
    limiter = RateLimiter()

    @asynccontextmanager
    async def lifespan(app):
        stop = threading.Event()
        thread = threading.Thread(target=worker, args=(factory, stop), daemon=True)
        app.state.worker_thread = thread
        if start_worker:
            thread.start()
        yield
        stop.set()
        if start_worker:
            thread.join(timeout=65)
        engine.dispose()

    app = FastAPI(title='Social Ear', version='0.2.0', lifespan=lifespan)
    app.state.factory = factory
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(','))

    @app.middleware('http')
    async def protect(request, call_next):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            origin = request.headers.get('origin')
            expected = os.environ.get('PUBLIC_ORIGIN', str(request.base_url).rstrip('/'))
            if origin and origin != expected:
                return Response('Cross-origin request rejected', status_code=403)
            try:
                size = int(request.headers.get('content-length', '0'))
            except ValueError:
                return Response('Invalid content length', status_code=400)
            if size > 2 * 1024 * 1024:
                return Response('Request exceeds 2 MB', status_code=413)
            if 'transfer-encoding' in request.headers:
                return Response('Send a Content-Length header; chunked uploads are not supported.', status_code=411)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        if os.environ.get('COOKIE_SECURE') == '1':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    def identity(request, db, write=False):
        token = request.cookies.get('social_ear', '')
        session = db.get(Session, token_hash(token))
        if not session or session.expires < time.time():
            raise HTTPException(401, 'Sign in to continue.')
        if write and not secrets.compare_digest(request.headers.get('x-csrf-token', ''), session.csrf):
            raise HTTPException(403, 'Invalid session protection token. Refresh and try again.')
        return db.get(User, session.user_id), session

    def access(request, db, workspace, write=False, owner=False):
        user, session = identity(request, db, write)
        member = db.scalar(select(Membership).where(Membership.workspace_id == workspace, Membership.user_id == user.id))
        if not member:
            raise HTTPException(404, 'Workspace not found.')
        if (write and member.role == 'viewer') or (owner and member.role != 'owner'):
            raise HTTPException(403, 'Your workspace role does not allow this action.')
        return user, member

    def login_response(db, user, response):
        raw = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        db.execute(delete(Session).where(Session.expires < time.time()))
        db.add(Session(token=token_hash(raw), user_id=user.id, csrf=csrf, expires=time.time()+86400))
        response.set_cookie('social_ear', raw, httponly=True, secure=os.environ.get('COOKIE_SECURE') == '1', samesite='lax', max_age=86400, path='/')
        return {'name': user.name, 'csrf': csrf}

    @app.get('/api/health')
    def health():
        if start_worker and hasattr(app.state, 'worker_thread') and not app.state.worker_thread.is_alive():
            raise HTTPException(503, 'Background worker is unavailable.')
        with factory() as db:
            db.execute(select(1))
        return {'status': 'ok', 'version': '0.2.0'}

    @app.post('/api/auth/register', status_code=201)
    def register(body: Credentials, request: Request, response: Response):
        if os.environ.get('ALLOW_REGISTRATION', '1') != '1':
            raise HTTPException(403, 'Registration is disabled by the administrator.')
        if not limiter.allow(request.client.host):
            raise HTTPException(429, 'Too many attempts. Try again in five minutes.')
        try:
            with factory.begin() as db:
                user = User(email=body.email.lower(), name=body.name, password=hash_password(body.password))
                workspace = Workspace(name=body.name + "’s workspace")
                db.add_all([user, workspace]); db.flush()
                db.add(Membership(user_id=user.id, workspace_id=workspace.id, role='owner'))
                audit(db, workspace.id, user.email, 'workspace.created', {})
                result = login_response(db, user, response)
            return result
        except IntegrityError:
            raise HTTPException(409, 'Unable to register with that email. Try signing in.')

    @app.post('/api/auth/login')
    def login(body: Credentials, request: Request, response: Response):
        if not limiter.allow(request.client.host):
            raise HTTPException(429, 'Too many attempts. Try again in five minutes.')
        with factory.begin() as db:
            user = db.scalar(select(User).where(User.email == body.email.lower()))
            valid = verify_password(body.password, user.password if user else dummy_password)
            if not user or not valid:
                raise HTTPException(401, 'Invalid email or password.')
            return login_response(db, user, response)

    dummy_password = hash_password(secrets.token_urlsafe(32))

    @app.get('/api/me')
    def me(request: Request):
        with factory() as db:
            user, session = identity(request, db)
            memberships = list(db.scalars(select(Membership).where(Membership.user_id == user.id)))
            return {'name': user.name, 'email': user.email, 'csrf': session.csrf,
                    'workspaces': [{'id': m.workspace_id, 'name': db.get(Workspace, m.workspace_id).name, 'role': m.role} for m in memberships]}

    @app.post('/api/auth/logout')
    def logout(request: Request, response: Response):
        with factory.begin() as db:
            _, session = identity(request, db, True)
            db.delete(session)
        response.delete_cookie('social_ear', path='/')
        return {'ok': True}

    @app.post('/api/workspaces', status_code=201)
    def create_workspace(body: WorkspaceInput, request: Request):
        with factory.begin() as db:
            user, _ = identity(request, db, True)
            count = len(list(db.scalars(select(Membership).where(Membership.user_id == user.id))))
            if count >= 20:
                raise HTTPException(409, 'Workspace limit reached.')
            workspace = Workspace(name=body.name); db.add(workspace); db.flush()
            db.add(Membership(user_id=user.id, workspace_id=workspace.id, role='owner'))
            return {'id': workspace.id}

    @app.get('/api/w/{workspace}/members')
    def members(workspace: str, request: Request):
        with factory() as db:
            access(request, db, workspace)
            return [{'email': db.get(User, m.user_id).email, 'role': m.role} for m in db.scalars(select(Membership).where(Membership.workspace_id == workspace))]

    @app.post('/api/w/{workspace}/members')
    def add_member(workspace: str, body: MemberInput, request: Request):
        with factory.begin() as db:
            user, _ = access(request, db, workspace, True, True)
            target = db.scalar(select(User).where(User.email == body.email.lower()))
            if not target:
                raise HTTPException(404, 'Ask this teammate to register first.')
            member = db.scalar(select(Membership).where(Membership.workspace_id == workspace, Membership.user_id == target.id))
            if member:
                if member.role == 'owner':
                    raise HTTPException(409, 'Owner role cannot be changed here.')
                member.role = body.role
            else:
                db.add(Membership(user_id=target.id, workspace_id=workspace, role=body.role))
            audit(db, workspace, user.email, 'member.updated', {'email': target.email, 'role': body.role})
            return {'ok': True}

    @app.get('/api/w/{workspace}/posts')
    def conversations(workspace: str, request: Request, q: str = '', sentiment: str = '', source: str = '', start: str = '', end: str = '', page: int = 1, page_size: int = 25):
        if page < 1 or not 1 <= page_size <= 100 or len(q) > 500:
            raise HTTPException(422, 'Invalid pagination or query.')
        for value in (start, end):
            if value:
                try: date.fromisoformat(value)
                except ValueError: raise HTTPException(422, 'Use ISO dates.')
        with factory() as db:
            access(request, db, workspace)
            data = posts(db, workspace, q, sentiment, source, start, end)
            return {'posts': data[(page-1)*page_size:page*page_size], 'summary': overview(data), 'page': page, 'page_size': page_size}

    @app.post('/api/w/{workspace}/import', status_code=202)
    async def import_csv(workspace: str, request: Request):
        content = await request.body()
        if not content or len(content) > 2*1024*1024:
            raise HTTPException(413, 'Upload a CSV between 1 byte and 2 MB.')
        try:
            text = content.decode('utf-8-sig')
        except UnicodeError:
            raise HTTPException(422, 'CSV must use UTF-8 encoding.')
        with factory.begin() as db:
            user, _ = access(request, db, workspace, True)
            pending = list(db.scalars(select(Job).where(Job.workspace_id == workspace, Job.state.in_(['pending', 'running']))))
            if len(pending) >= 5:
                raise HTTPException(429, 'Wait for existing jobs to finish.')
            job = Job(workspace_id=workspace, kind='import', payload={'csv': text})
            db.add(job); db.flush()
            audit(db, workspace, user.email, 'import.queued', {'job_id': job.id})
            return {'id': job.id, 'state': 'pending'}

    @app.patch('/api/w/{workspace}/posts/{post_id}')
    def review(workspace: str, post_id: str, body: ReviewInput, request: Request):
        with factory.begin() as db:
            user, _ = access(request, db, workspace, True)
            record = db.get(Record, post_id)
            if not record or record.workspace_id != workspace or record.kind != 'post':
                raise HTTPException(404, 'Conversation not found.')
            if body.assignee:
                target = db.scalar(select(User).where(User.email == body.assignee.lower()))
                if not target or not db.scalar(select(Membership).where(Membership.workspace_id == workspace, Membership.user_id == target.id)):
                    raise HTTPException(422, 'Assignee must be a workspace member.')
            payload = {**record.payload, 'sentiment': body.sentiment, 'reviewed': True, 'status': body.status, 'assignee': body.assignee.lower()}
            if body.note:
                from .database import now
                payload['notes'] = [*payload['notes'], {'author': user.email, 'text': body.note, 'created_at': now()}][-100:]
            record.payload = payload
            audit(db, workspace, user.email, 'post.reviewed', {'id': post_id})
            return serialize(record)

    @app.get('/api/w/{workspace}/export')
    def export(workspace: str, request: Request, q: str = '', sentiment: str = '', source: str = '', start: str = '', end: str = ''):
        with factory() as db:
            access(request, db, workspace)
            data = posts(db, workspace, q, sentiment, source, start, end)
        output = io.StringIO(newline='')
        fields = ['id', 'text', 'source', 'published_at', 'sentiment', 'language', 'status', 'assignee']
        writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader()
        for post in data:
            writer.writerow({key: ("'"+str(post.get(key, '')) if str(post.get(key, '')).lstrip().startswith(('=', '+', '-', '@')) else post.get(key, '')) for key in fields})
        return Response(output.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="social-ear.csv"'})

    @app.get('/api/w/{workspace}/activity')
    def activity(workspace: str, request: Request):
        with factory() as db:
            access(request, db, workspace)
            result = {kind: [serialize(r) for r in records(db, workspace, kind)[:100]] for kind in ('monitor', 'alert', 'report', 'audit', 'schedule')}
            data = posts(db, workspace)
            comparisons = []
            for record in records(db, workspace, 'competitor'):
                matched = [p for p in data if record.payload['keyword'].casefold() in p['text'].casefold()]
                comparisons.append({**serialize(record), 'total': len(matched),
                                    'positive': sum(p['sentiment'] == 'positive' for p in matched),
                                    'negative': sum(p['sentiment'] == 'negative' for p in matched)})
            result['competitor'] = comparisons
            return result

    @app.post('/api/w/{workspace}/competitors', status_code=201)
    def competitor(workspace: str, body: CompetitorInput, request: Request):
        with factory.begin() as db:
            user, _ = access(request, db, workspace, True)
            if len(records(db, workspace, 'competitor')) >= 20:
                raise HTTPException(409, 'Comparison limit reached.')
            entry = Record(workspace_id=workspace, kind='competitor', payload=body.model_dump())
            db.add(entry); db.flush()
            audit(db, workspace, user.email, 'competitor.created', body.model_dump())
            return serialize(entry)

    @app.post('/api/w/{workspace}/report-schedule')
    def schedule_report(workspace: str, body: ScheduleInput, request: Request):
        with factory.begin() as db:
            user, _ = access(request, db, workspace, True)
            existing = records(db, workspace, 'schedule')
            payload = {**body.model_dump(), 'next_run': time.time()+body.interval_hours*3600}
            if existing:
                existing[0].payload = payload
            else:
                db.add(Record(workspace_id=workspace, kind='schedule', payload=payload))
            audit(db, workspace, user.email, 'report.schedule.updated', body.model_dump())
            return payload

    @app.post('/api/w/{workspace}/monitors', status_code=201)
    def monitor(workspace: str, body: MonitorInput, request: Request):
        with factory.begin() as db:
            user, _ = access(request, db, workspace, True)
            if len(records(db, workspace, 'monitor')) >= 30:
                raise HTTPException(409, 'Monitor limit reached.')
            entry = Record(workspace_id=workspace, kind='monitor', payload=body.model_dump()); db.add(entry); db.flush()
            evaluate_monitors(db, workspace)
            audit(db, workspace, user.email, 'monitor.created', body.model_dump())
            return serialize(entry)

    @app.post('/api/w/{workspace}/alerts/{alert_id}/acknowledge')
    def acknowledge(workspace: str, alert_id: str, request: Request):
        with factory.begin() as db:
            user, _ = access(request, db, workspace, True)
            record = db.get(Record, alert_id)
            if not record or record.workspace_id != workspace or record.kind != 'alert':
                raise HTTPException(404, 'Alert not found.')
            record.payload = {**record.payload, 'status': 'acknowledged'}
            audit(db, workspace, user.email, 'alert.acknowledged', {'id': alert_id})
            return {'ok': True}

    @app.get('/api/w/{workspace}/jobs')
    def jobs(workspace: str, request: Request):
        with factory() as db:
            access(request, db, workspace)
            return [{'id': j.id, 'kind': j.kind, 'state': j.state, 'created_at': j.created_at, 'result': j.result} for j in db.scalars(select(Job).where(Job.workspace_id == workspace).order_by(Job.created_at.desc()).limit(30))]

    @app.post('/api/w/{workspace}/jobs/{job_id}/retry')
    def retry(workspace: str, job_id: str, request: Request):
        with factory.begin() as db:
            access(request, db, workspace, True)
            job = db.get(Job, job_id)
            if not job or job.workspace_id != workspace:
                raise HTTPException(404, 'Job not found.')
            if job.state != 'failed' or job.attempts >= 3:
                raise HTTPException(409, 'Only failed jobs with fewer than three attempts can be retried.')
            job.state = 'pending'
            return {'ok': True}

    @app.post('/api/w/{workspace}/reports', status_code=202)
    def queue_report(workspace: str, request: Request):
        with factory.begin() as db:
            access(request, db, workspace, True)
            job = Job(workspace_id=workspace, kind='report', payload={}); db.add(job); db.flush()
            return {'id': job.id}

    @app.post('/api/w/{workspace}/reanalyze', status_code=202)
    def reanalyze(workspace: str, request: Request):
        with factory.begin() as db:
            access(request, db, workspace, True)
            job = Job(workspace_id=workspace, kind='reanalyze', payload={}); db.add(job); db.flush()
            return {'id': job.id}

    @app.post('/api/w/{workspace}/research')
    def assistant(workspace: str, body: Question, request: Request):
        with factory() as db:
            access(request, db, workspace)
            return research(body.question, posts(db, workspace))

    @app.get('/api/w/{workspace}/connectors')
    def connectors(workspace: str, request: Request):
        with factory() as db:
            access(request, db, workspace)
        return {'bluesky': os.environ.get('ENABLE_BLUESKY') == '1', 'csv': True}

    @app.post('/api/w/{workspace}/connectors/bluesky', status_code=202)
    def collect(workspace: str, body: ConnectorInput, request: Request):
        if os.environ.get('ENABLE_BLUESKY') != '1':
            raise HTTPException(409, 'Set ENABLE_BLUESKY=1 on the server to enable public search. Queries are sent to Bluesky.')
        with factory.begin() as db:
            access(request, db, workspace, True)
            if not limiter.allow('bluesky:'+workspace, limit=5, window=300):
                raise HTTPException(429, 'Collection limit reached. Try again in five minutes.')
            job = Job(workspace_id=workspace, kind='bluesky', payload=body.model_dump()); db.add(job); db.flush()
            return {'id': job.id}

    @app.get('/')
    def index():
        return FileResponse(ROOT / 'web' / 'index.html')

    @app.get('/app.js')
    def javascript():
        return FileResponse(ROOT / 'web' / 'app.js', media_type='text/javascript')

    @app.get('/style.css')
    def stylesheet():
        return FileResponse(ROOT / 'web' / 'style.css', media_type='text/css')

    return app
