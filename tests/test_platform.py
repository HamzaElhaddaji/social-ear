import csv
import io
import tempfile
import unittest
import os
from uuid import uuid4
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import create_engine, text
from app.api import create_app
from app.database import Job, Record
from app.service import run_job, schedule_due
from app.intelligence import analyze


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        url = os.environ.get('TEST_DATABASE_URL')
        self.pg_engine = None
        if url:
            # Each CI test owns its randomly named schema, never application tables.
            self.pg_schema = 'test_' + uuid4().hex
            self.pg_engine = create_engine(url)
            with self.pg_engine.begin() as db:
                db.execute(text('CREATE SCHEMA ' + self.pg_schema))
            url += ('&' if '?' in url else '?') + 'options=-csearch_path%3D' + self.pg_schema
        self.app = create_app(url or 'sqlite:///'+str(Path(self.temp.name)/'platform.db'), start_worker=False)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.register('owner@example.com')

    def tearDown(self):
        self.client.__exit__(None, None, None)
        if self.pg_engine:
            with self.pg_engine.begin() as db:
                db.execute(text('DROP SCHEMA ' + self.pg_schema + ' CASCADE'))
            self.pg_engine.dispose()
        self.temp.cleanup()

    def register(self, email):
        result = self.client.post('/api/auth/register', json={'email': email, 'name':'Researcher', 'password':'a-long-test-password-2026'})
        self.assertEqual(result.status_code, 201, result.text)
        self.csrf = result.json()['csrf']
        self.workspace = self.client.get('/api/me').json()['workspaces'][0]['id']

    def write(self, path, data=None, method='POST', content=None):
        return self.client.request(method, '/api/w/'+self.workspace+path, json=data, content=content, headers={'X-CSRF-Token':self.csrf})

    def import_data(self, text='text,source\nThe support team is wonderful and helpful,Reviews\nThe application is awful and broken,Community\n'):
        response = self.write('/import', content=text.encode())
        self.assertEqual(response.status_code, 202, response.text)
        identity = response.json()['id']
        run_job(self.app.state.factory, identity)
        return identity

    def get(self, path):
        return self.client.get('/api/w/'+self.workspace+path)

    def test_register_login_logout_and_expired_session(self):
        self.assertEqual(self.client.post('/api/auth/logout', headers={'X-CSRF-Token':self.csrf}).status_code, 200)
        self.assertEqual(self.client.get('/api/me').status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={'email':'owner@example.com','password':'incorrect-password'}).status_code, 401)
        response = self.client.post('/api/auth/login', json={'email':'owner@example.com','password':'a-long-test-password-2026'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('HttpOnly', response.headers['set-cookie'])

    def test_csrf_origin_host_and_unauthenticated_access(self):
        self.assertEqual(self.client.post('/api/w/'+self.workspace+'/reports').status_code, 403)
        response = self.client.post('/api/w/'+self.workspace+'/reports', headers={'Origin':'https://attacker.example','X-CSRF-Token':self.csrf})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get('/api/health', headers={'Host':'evil.example'}).status_code, 400)
        self.client.cookies.clear()
        self.assertEqual(self.get('/posts').status_code, 401)

    def test_cross_workspace_isolation_for_posts_jobs_and_activity(self):
        old_workspace = self.workspace
        job = self.import_data()
        post = self.get('/posts').json()['posts'][0]
        self.register('other@example.com')
        self.assertEqual(self.client.get('/api/w/'+old_workspace+'/posts').status_code, 404)
        self.assertEqual(self.get('/posts').json()['summary']['total'], 0)
        self.assertEqual(self.write('/posts/'+post['id'], {'sentiment':'positive'}, method='PATCH').status_code, 404)
        self.assertEqual(self.write('/jobs/'+job+'/retry').status_code, 404)
        self.assertEqual(self.get('/activity').json()['audit'][0]['action'], 'workspace.created')

    def test_import_deduplication_pagination_filter_and_export(self):
        self.import_data(); self.import_data()
        response = self.get('/posts?page_size=1')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()['posts']), 1)
        self.assertEqual(response.json()['summary']['total'], 2)
        self.assertEqual(self.get('/posts?sentiment=negative').json()['summary']['total'], 1)
        self.assertEqual(self.get('/posts?source=Reviews').json()['summary']['total'], 1)
        self.assertEqual(self.get('/posts?page=0').status_code, 422)
        self.import_data('text\n=SUM(A1)\n')
        rows = list(csv.DictReader(io.StringIO(self.get('/export').text)))
        self.assertTrue(any(row['text'].startswith("'=SUM") for row in rows))

    def test_failed_job_rolls_back_partial_import_and_retry(self):
        job_id = self.import_data('text,published_at\nA good post,2026-10-19\nAnother post,invalid\n')
        self.assertEqual(self.get('/posts').json()['summary']['total'], 0)
        job = self.get('/jobs').json()[0]
        self.assertEqual(job['state'], 'failed')
        self.assertIn('ISO', job['result']['error'])
        self.assertEqual(self.write('/jobs/'+job_id+'/retry').status_code, 200)

    def test_viewer_cannot_mutate_and_analyst_cannot_manage_members(self):
        workspace, csrf = self.workspace, self.csrf
        self.register('viewer@example.com')
        self.client.post('/api/auth/logout', headers={'X-CSRF-Token':self.csrf})
        login = self.client.post('/api/auth/login',json={'email':'owner@example.com','password':'a-long-test-password-2026'})
        self.csrf, self.workspace = login.json()['csrf'], workspace
        self.assertEqual(self.write('/members',{'email':'viewer@example.com','role':'viewer'}).status_code, 200)
        login = self.client.post('/api/auth/login',json={'email':'viewer@example.com','password':'a-long-test-password-2026'})
        self.csrf = login.json()['csrf']
        self.assertEqual(self.get('/posts').status_code, 200)
        self.assertEqual(self.write('/reports').status_code, 403)
        self.assertEqual(self.write('/members',{'email':'owner@example.com','role':'analyst'}).status_code, 403)

    def test_review_assignment_notes_and_audit(self):
        self.import_data()
        post = self.get('/posts').json()['posts'][0]
        body = {'sentiment':'neutral', 'status':'investigating','assignee':'owner@example.com','note':'Checking this report.'}
        result = self.write('/posts/'+post['id'], body, method='PATCH')
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()['reviewed'])
        self.assertEqual(result.json()['notes'][0]['text'], body['note'])
        body['assignee']='outsider@example.com'
        self.assertEqual(self.write('/posts/'+post['id'], body, method='PATCH').status_code, 422)
        self.assertEqual(self.get('/activity').json()['audit'][0]['action'], 'post.reviewed')

    def test_monitor_alert_dedup_and_acknowledgement(self):
        self.write('/monitors',{'name':'Support signal','keyword':'support','threshold':1})
        today = datetime.now(timezone.utc).isoformat()
        self.import_data('text,published_at\nSupport is terrible and very slow,'+today+'\n')
        alerts = self.get('/activity').json()['alert']
        self.assertEqual(len(alerts), 1)
        self.import_data('text,published_at\nSupport is terrible and very slow,'+today+'\n')
        self.assertEqual(len(self.get('/activity').json()['alert']), 1)
        self.assertEqual(self.write('/alerts/'+alerts[0]['id']+'/acknowledge').status_code, 200)

    def test_report_research_and_schedule(self):
        self.import_data()
        answer = self.write('/research',{'question':'What about the support team?'})
        self.assertEqual(answer.status_code, 200)
        self.assertTrue(answer.json()['citations'])
        known = {p['id'] for p in self.get('/posts').json()['posts']}
        self.assertTrue(all(c['id'] in known for c in answer.json()['citations']))
        job = self.write('/reports').json()['id']; run_job(self.app.state.factory, job)
        self.assertEqual(self.get('/activity').json()['report'][0]['summary']['total'], 2)
        self.write('/report-schedule',{'interval_hours':24,'enabled':True})
        with self.app.state.factory.begin() as db:
            entry = db.scalar(select(Record).where(Record.kind=='schedule'))
            entry.payload = {**entry.payload, 'next_run':0}
        schedule_due(self.app.state.factory); schedule_due(self.app.state.factory)
        with self.app.state.factory() as db:
            queued = list(db.scalars(select(Job).where(Job.state=='pending', Job.kind=='report')))
        self.assertEqual(len(queued), 1)

    def test_connector_disabled_and_mocked_provider(self):
        self.assertEqual(self.write('/connectors/bluesky',{'query':'brand'}).status_code, 409)
        with patch.dict('os.environ',{'ENABLE_BLUESKY':'1'}):
            job = self.write('/connectors/bluesky',{'query':'brand'}).json()['id']
            with patch('app.connectors.bluesky', return_value=[{'text':'A wonderful product with great support','source':'Bluesky'}]):
                run_job(self.app.state.factory, job)
        self.assertEqual(self.get('/posts').json()['summary']['total'], 1)

    def test_language_provenance_and_empty_research(self):
        result = analyze('Ce service est vraiment excellent et je suis très content de cette expérience.')
        self.assertEqual(result['language'], 'fr')
        self.assertEqual(result['sentiment'], 'unclassified')
        self.assertEqual(result['model'], 'vader-3.3.2-domain-v1')
        self.assertEqual(self.write('/research',{'question':'support'}).json()['citations'], [])

    def test_product_complaints_are_not_mistaken_for_positive_support(self):
        self.assertEqual(analyze('I cannot log in and support is not responding.')['sentiment'], 'negative')
        self.assertEqual(analyze('The price is too expensive for small teams.')['sentiment'], 'negative')

    def test_comparisons_and_reanalysis_preserve_review(self):
        self.import_data()
        self.assertEqual(self.write('/competitors',{'name':'Support','keyword':'support'}).status_code, 201)
        self.assertEqual(self.get('/activity').json()['competitor'][0]['total'], 1)
        post=self.get('/posts').json()['posts'][0]
        self.write('/posts/'+post['id'],{'sentiment':'neutral'},method='PATCH')
        job=self.write('/reanalyze').json()['id'];run_job(self.app.state.factory,job)
        result=self.get('/posts').json()['posts']
        self.assertEqual(next(p for p in result if p['id']==post['id'])['sentiment'],'neutral')

    def test_import_normalizes_dates_to_utc(self):
        self.import_data('text,published_at\nAn excellent product with great support,2026-10-19T01:00:00+02:00\n')
        post=self.get('/posts').json()['posts'][0]
        self.assertEqual(post['published_at'],'2026-10-18T23:00:00+00:00')
        self.assertEqual(self.get('/posts?start=2026-10-19').json()['summary']['total'],0)


if __name__ == '__main__':
    unittest.main()
