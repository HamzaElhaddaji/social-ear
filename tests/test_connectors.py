import os
import unittest
from unittest.mock import patch
import httpx
from app.connectors import mastodon, youtube, request_json


class ConnectorTests(unittest.TestCase):
    def test_mastodon_normalizes_public_html_and_keeps_provenance(self):
        payload=[{'id':'123','content':'<p>Great &amp; helpful!</p><script>danger()</script>','visibility':'public','created_at':'2026-10-19T00:00:00Z','url':'https://mastodon.social/@test/123'},
                 {'id':'private','content':'Secret','visibility':'private'}]
        with patch('app.connectors.request_json',return_value=payload):data=mastodon('#opensource')
        self.assertEqual(len(data),1);self.assertEqual(data[0]['text'],'Great & helpful!')
        self.assertEqual(data[0]['remote_id'],'123');self.assertTrue(data[0]['url'].startswith('https://'))

    def test_mastodon_rejects_path_injection(self):
        with patch('app.connectors.request_json') as call:
            with self.assertRaises(ValueError):mastodon('../internal?query=secret')
        call.assert_not_called()

    def test_youtube_requires_valid_video_and_server_key(self):
        with patch.dict(os.environ,{'YOUTUBE_API_KEY':''}):
            with self.assertRaises(ValueError):youtube('abcdefghijk')
        with self.assertRaises(ValueError):youtube('https://youtube.com/watch?v=anything')

    def test_youtube_normalizes_top_level_comment_and_limits_quota(self):
        payload={'items':[{'snippet':{'topLevelComment':{'id':'comment1','snippet':{'textOriginal':'Wonderful support!','publishedAt':'2026-10-19T00:00:00Z'}}}}]}
        with patch.dict(os.environ,{'YOUTUBE_API_KEY':'test-only-key'}),patch('app.connectors.request_json',return_value=payload) as call:
            data=youtube('abcdefghijk')
        self.assertEqual(data[0]['source'],'YouTube');self.assertEqual(data[0]['remote_id'],'comment1')
        self.assertEqual(call.call_args.kwargs['params']['maxResults'],100)

    def test_retry_is_bounded_and_error_does_not_reveal_key(self):
        responses=[httpx.Response(429),httpx.Response(503),httpx.Response(403,json={'error':'secret-key'})]
        with patch('app.connectors.httpx.get',side_effect=responses) as call,patch('app.connectors.time.sleep'):
            with self.assertRaises(ValueError) as error:request_json('https://www.googleapis.com/youtube/v3/commentThreads',{'key':'secret-key'})
        self.assertEqual(call.call_count,3);self.assertNotIn('secret-key',str(error.exception))

    def test_network_errors_are_redacted(self):
        with patch('app.connectors.httpx.get',side_effect=httpx.ConnectError('secret in URL')),patch('app.connectors.time.sleep'):
            with self.assertRaises(ValueError) as error:request_json('https://example.test')
        self.assertNotIn('secret in URL',str(error.exception))
