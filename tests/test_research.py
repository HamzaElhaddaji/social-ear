import json
import os
import unittest
from unittest.mock import patch
import httpx
from app.research import answer, endpoint, GenerationUnavailable

POSTS=[{'id':'post-1','text':'The support team was rude and very unhelpful.','source':'Reviews','sentiment':'negative'}]


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.config=patch.dict(os.environ,{'RESEARCH_PROVIDER':'ollama','OLLAMA_URL':'http://127.0.0.1:11434','OLLAMA_MODEL':'test-local-model'})
        self.config.start();self.addCleanup(self.config.stop)

    def response(self, claims):
        return httpx.Response(200,json={'done':True,'message':{'content':json.dumps({'claims':claims})}})

    def test_structured_generation_validates_existing_citations(self):
        with patch('app.research.httpx.post',return_value=self.response([{'text':'A reviewer reports poor support.','evidence_ids':['post-1']}])) as call:
            result=answer('What about support?',POSTS)
        self.assertEqual(result['method'],'ollama-grounded-generation')
        self.assertEqual(result['citations'][0]['id'],'post-1')
        sent=call.call_args.kwargs['json']
        self.assertEqual(sent['options']['temperature'],0)
        self.assertNotIn('tools',sent)
        self.assertIn('untrusted',sent['messages'][0]['content'])

    def test_hallucinated_citation_rejected(self):
        with patch('app.research.httpx.post',return_value=self.response([{'text':'Unsupported claim.','evidence_ids':['other-workspace-id']}])):
            with self.assertRaises(GenerationUnavailable):answer('support',POSTS)

    def test_uncited_or_empty_generation_rejected(self):
        for claims in ([],[{'text':'Uncited','evidence_ids':[]}]):
            with patch('app.research.httpx.post',return_value=self.response(claims)):
                with self.assertRaises(GenerationUnavailable):answer('support',POSTS)

    def test_timeout_and_malformed_model_output(self):
        with patch('app.research.httpx.post',side_effect=httpx.ConnectError('offline')):
            with self.assertRaises(GenerationUnavailable):answer('support',POSTS)
        with patch('app.research.httpx.post',return_value=httpx.Response(200,json={'done':True,'message':{'content':'not JSON'}})):
            with self.assertRaises(GenerationUnavailable):answer('support',POSTS)

    def test_no_evidence_means_no_generation_call(self):
        with patch('app.research.httpx.post') as call:
            result=answer('support',[])
        call.assert_not_called();self.assertEqual(result['citations'],[])

    def test_remote_or_credentialed_endpoint_is_rejected(self):
        for value in ['https://remote.example:11434','http://user:pass@localhost:11434','http://localhost:11434/other','http://169.254.169.254:11434']:
            with patch.dict(os.environ,{'OLLAMA_URL':value}):
                with self.assertRaises(GenerationUnavailable):endpoint()
