import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from app.config import load_local_config
from app.research import answer, configuration, GenerationUnavailable

POSTS=[{'id':'evidence-1','text':'The support team was rude and very unhelpful.','source':'Synthetic test','sentiment':'negative'}]


class GroqTests(unittest.TestCase):
    def setUp(self):
        config=patch.dict(os.environ,{'RESEARCH_PROVIDER':'groq','GROQ_API_KEY':'test-secret-never-real','GROQ_MODEL':'openai/gpt-oss-20b'})
        config.start();self.addCleanup(config.stop)

    def response(self,ids=None,finish='stop'):
        return httpx.Response(200,json={'choices':[{'finish_reason':finish,'message':{'content':json.dumps({'claims':[{'text':'A reviewer reports poor support.','evidence_ids':ids or ['evidence-1']}]})}}]})

    def test_hosted_request_uses_fixed_endpoint_bounded_evidence_and_secret_header(self):
        with patch('app.research.httpx.post',return_value=self.response()) as call:
            result=answer('What about support?',POSTS)
        self.assertEqual(result['method'],'groq-grounded-generation')
        self.assertEqual(call.call_args.args[0],'https://api.groq.com/openai/v1/chat/completions')
        self.assertEqual(call.call_args.kwargs['headers']['Authorization'],'Bearer test-secret-never-real')
        payload=call.call_args.kwargs['json']
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertFalse(call.call_args.kwargs['follow_redirects'])
        self.assertNotIn('test-secret',json.dumps(result))
        self.assertNotIn('GROQ_API_KEY',configuration())

    def test_missing_key_never_sends_request(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':''}),patch('app.research.httpx.post') as call:
            with self.assertRaises(GenerationUnavailable):answer('support',POSTS)
        call.assert_not_called()

    def test_auth_quota_and_provider_errors_are_redacted(self):
        for status in (401,403,429,500):
            with self.subTest(status=status),patch('app.research.httpx.post',return_value=httpx.Response(status,json={'error':'test-secret-never-real'})):
                with self.assertRaises(GenerationUnavailable) as error:answer('support',POSTS)
                self.assertNotIn('test-secret',str(error.exception))

    def test_unknown_citations_incomplete_and_malformed_answers_fail_closed(self):
        for response in (self.response(['unknown-workspace-post']),self.response(finish='length'),httpx.Response(200,json={'choices':[]})):
            with patch('app.research.httpx.post',return_value=response):
                with self.assertRaises(GenerationUnavailable):answer('support',POSTS)

    def test_cloud_requests_never_send_unrelated_posts(self):
        data=POSTS+[{'id':'private-unrelated','text':'A completely unrelated kitchen recipe.','source':'Other','sentiment':'neutral'}]
        with patch('app.research.httpx.post',return_value=self.response()) as call:answer('support',data)
        self.assertNotIn('private-unrelated',call.call_args.kwargs['json']['messages'][1]['content'])


class ConfigTests(unittest.TestCase):
    def test_env_loader_preserves_process_override_and_does_not_expand_code(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'SOCIALEAR_TEST_OVERRIDE':'process'}):
            path=Path(folder)/'.env'
            path.write_text('SOCIALEAR_TEST_OVERRIDE=file\nSOCIALEAR_TEST_LITERAL=$(do-not-run)\nSOCIALEAR_TEST_QUOTED="hello"\n',encoding='utf-8')
            try:
                load_local_config(path)
                self.assertEqual(os.environ['SOCIALEAR_TEST_OVERRIDE'],'process')
                self.assertEqual(os.environ['SOCIALEAR_TEST_LITERAL'],'$(do-not-run)')
                self.assertEqual(os.environ['SOCIALEAR_TEST_QUOTED'],'hello')
            finally:
                os.environ.pop('SOCIALEAR_TEST_LITERAL',None);os.environ.pop('SOCIALEAR_TEST_QUOTED',None)
