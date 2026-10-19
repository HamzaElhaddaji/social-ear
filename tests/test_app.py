import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from app.analysis import sentiment
from app.store import Store
from app.server import make_handler


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'test.db')

    def tearDown(self):
        self.temp.cleanup()

    def test_import_dedup_search_and_persistence(self):
        content = 'text,source\n"Great, helpful support",Reviews\nBroken login,Community\n,Empty\n'
        self.assertEqual(self.store.import_csv(content), {'imported': 2, 'duplicates': 0, 'empty': 1})
        self.assertEqual(self.store.import_csv(content)['duplicates'], 2)
        self.assertEqual(Store(self.store.path).posts('login', 'negative')[0]['source'], 'Community')

    def test_invalid_import_is_atomic(self):
        with self.assertRaises(ValueError):
            self.store.import_csv('text\nGood\n' + 'x' * 20001)
        self.assertEqual(self.store.posts(), [])
        with self.assertRaises(ValueError):
            self.store.import_csv('message\nHello')

    def test_baseline_negation(self):
        self.assertEqual(sentiment('not good'), 'negative')
        self.assertEqual(sentiment('not terrible'), 'positive')
        self.assertEqual(sentiment('bonjour'), 'neutral')

    def test_http_import_filter_export_and_origin(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.store))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            request = Request(base+'/api/import', data=b'text\nGreat support\n=SUM(A1)\n', method='POST')
            with urlopen(request) as response:
                self.assertEqual(json.load(response)['imported'], 2)
            with urlopen(base+'/api/posts?sentiment=positive') as response:
                self.assertEqual(json.load(response)['summary']['total'], 1)
            with urlopen(base+'/api/export') as response:
                self.assertIn("'=SUM(A1)", response.read().decode())
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base+'/api/import', data=b'text\nBad', headers={'Origin':'https://other.example'}))
            self.assertEqual(error.exception.code, 403)
            with self.assertRaises(HTTPError):
                urlopen(base+'/../app/server.py')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
