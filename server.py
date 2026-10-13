"""Loopback HTTP interface. No request-body logging or persistence."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from ledger import Reviewer

ROOT = Path(__file__).parent/'web'


def make_handler(reviewer, port):
    allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
    origins = {f'http://{host}' for host in allowed_hosts}
    inference_lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body, kind='application/json'):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get('Host') not in allowed_hosts:
                return self.reply(403, {'error': 'Local host required.'})
            names = {'/':'index.html', '/app.js':'app.js', '/style.css':'style.css', '/sample.json':'sample.json'}
            types = {'.html':'text/html; charset=utf-8', '.css':'text/css', '.js':'text/javascript', '.json':'application/json'}
            if self.path not in names:
                return self.reply(404, {'error': 'Not found.'})
            f = ROOT/names[self.path]
            self.reply(200, f.read_bytes(), types[f.suffix])

        def do_POST(self):
            if self.headers.get('Host') not in allowed_hosts or self.headers.get('Origin') not in origins:
                return self.reply(403, {'error': 'Local browser origin required.'})
            if self.path != '/api/review':
                return self.reply(404, {'error': 'Not found.'})
            if self.headers.get('Content-Type') != 'application/json':
                return self.reply(415, {'error': 'JSON required.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 1 <= size <= 50000:
                    return self.reply(413, {'error': 'Body must be 1–50000 bytes.'})
                payload = json.loads(self.rfile.read(size))
                with inference_lock:
                    result = reviewer.analyze(payload)
                self.reply(200, result)
            except (ValueError, UnicodeError) as exc:
                self.reply(400, {'error': str(exc)})
            except Exception:
                self.reply(500, {'error': 'Local inference failed. Restart the app and retry.'})
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8798)
    args = parser.parse_args()
    reviewer = Reviewer()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(reviewer, args.port))
    print(f'Brief Ledger ready: http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()
