"""Run with python -m app.server. Local-only until authentication is added."""
import io
import csv
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .analysis import summarize
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
MAX_BODY = 2 * 1024 * 1024


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, payload, kind='application/json; charset=utf-8'):
            body = json.dumps(payload).encode() if kind.startswith('application/json') else payload
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            params = parse_qs(url.query)
            if url.path == '/api/health':
                return self.send(200, {'status': 'ok'})
            if url.path in ('/api/posts', '/api/export'):
                posts = store.posts(params.get('q', [''])[0], params.get('sentiment', [''])[0])
                if url.path == '/api/posts':
                    return self.send(200, {'posts': posts, 'summary': summarize(posts)})
                output = io.StringIO(newline='')
                writer = csv.DictWriter(output, fieldnames=['text', 'source', 'published_at', 'sentiment'])
                writer.writeheader()
                for post in posts:
                    writer.writerow({k: ("'" + str(post[k]) if str(post[k]).startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else post[k]) for k in writer.fieldnames})
                return self.send(200, output.getvalue().encode(), 'text/csv; charset=utf-8')
            files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
            if url.path not in files:
                return self.send(404, {'error': 'Not found'})
            name, kind = files[url.path]
            return self.send(200, (ROOT / 'web' / name).read_bytes(), kind + '; charset=utf-8')

        def do_POST(self):
            if self.path != '/api/import':
                return self.send(404, {'error': 'Not found'})
            # Prevent cross-origin browser requests from changing local data.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send(403, {'error': 'Cross-origin import rejected'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size <= 0 or size > MAX_BODY:
                    return self.send(413, {'error': 'Upload a CSV smaller than 2 MB.'})
                content = self.rfile.read(size).decode('utf-8-sig')
                result = store.import_csv(content)
            except (ValueError, UnicodeError, csv.Error):
                return self.send(400, {'error': 'Invalid CSV. Use UTF-8 with a text column; posts must be under 20,000 characters.'})
            return self.send(200, result)
    return Handler


if __name__ == '__main__':
    # Keep the original launch command compatible without exposing the legacy API.
    import uvicorn
    from .config import load_local_config
    load_local_config()
    from .api import create_app
    uvicorn.run(create_app(), host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '8000')))
