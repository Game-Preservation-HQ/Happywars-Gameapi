# Copyright (C) 2026 Serenity, Game Preservation HQ.
# SPDX-License-Identifier: AGPL-3.0-only

"""Checks for HappyWars.py against a fake gameapi that records what it gets.

    py tests/test_server.py
"""
import http.client
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WORK = tempfile.mkdtemp()
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'HappyWars.py')
fails = 0


def check(name, ok, extra=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({extra})' if extra and not ok else ''))
    fails += not ok


spec = importlib.util.spec_from_file_location('HappyWars', SCRIPT)
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)

S = 'https://gameapi.hwapi.live/api'
for path, want in (
        ('/gameapi/pollux/', S + '/pollux/'),
        ('/pollux/', S + '/pollux/'),
        ('/api/pollux/', S + '/pollux/'),
        ('/gameapi/api/pollux/', S + '/pollux/'),
        ('/purchasing/HappyTicketSum', S + '/HappyTicketSum'),
        ('/purchasingHappyTicketSum', S + '/HappyTicketSum'),
        ('/HappyTicketAsset', S + '/HappyTicketAsset'),
        ('/telemetry/TelemetryEntity/?name=recordingrestapiresult', S + '/TelemetryEntity/?name=recordingrestapiresult'),
        ('/sts/token?a=1', S + '/token?a=1'),
        ('/stsx/a', S + '/stsx/a'),
        ('/apix', S + '/apix')):
    got = hw.upstream_url(S, path)
    check(f'url {path}', got == want, got)
check('url, server without a path', hw.upstream_url('http://127.0.0.1:8099', '/gameapi/pollux/') == 'http://127.0.0.1:8099/pollux/')

seen = []


class FakeGameapi(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        seen.append({'method': self.command, 'path': self.path, 'headers': {k.lower(): v for k, v in self.headers.items()}, 'body': body})
        if self.path.startswith('/api/redirect'):
            status, reply, extra = 302, b'', [('Location', '/api/elsewhere')]
        elif self.path.startswith('/api/missing'):
            status, reply, extra = 404, b'{"error":"not here"}', []
        else:
            status, reply, extra = 200, json.dumps({'path': self.path, 'len': len(body)}).encode(), [('X-Test', 'yes')]
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        for k, v in extra:
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    do_GET = do_POST


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def start(*args):
    port = free_port()
    out = open(os.path.join(WORK, f'log{port}.txt'), 'w+', encoding='utf-8')
    p = subprocess.Popen([sys.executable, '-I', SCRIPT, '--port', str(port), *args],
                         stdout=out, stderr=subprocess.STDOUT, text=True)
    p.out = out
    for _ in range(100):
        try:
            socket.create_connection(('127.0.0.1', port), 0.2).close()
            return p, port
        except OSError:
            time.sleep(0.05)
    p.kill()
    sys.exit('HappyWars.py did not start: ' + stop(p))


def stop(p):
    p.terminate()
    p.wait(timeout=10)
    p.out.seek(0)
    text = p.out.read()
    p.out.close()
    return text


def post(port, path, body, headers=None, host='127.0.0.1', method='POST'):
    c = http.client.HTTPConnection(host, port, timeout=10)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    out = r.status, dict(r.getheaders()), r.read()
    c.close()
    return out


up = ThreadingHTTPServer(('127.0.0.1', 0), FakeGameapi)
threading.Thread(target=up.serve_forever, daemon=True).start()
UP = f'http://127.0.0.1:{up.server_address[1]}/api'

CLIENT_HEADERS = {'Connection': 'Keep-Alive', 'Accept': 'text/plain', 'User-Agent': 'WinHttpClient',
                  'x-xbl-contract-version': '1', 'X-Authorization': 'XBL2.0 x='}
pollux = b'version:Cores_EarlyAccess,f:CoreSaveDataLoad,userid:(null),pid:1234,xuid:DEBUG_CLIENT_XUID'
tickets = b'{"steamid":1234,"appid":246280}'
telemetry = b'UserID:(null),NR:1,SaveLoadType:2,SaveLoadResult:0,SaveLoadHttpCode:0'

p, port = start('--host', '127.0.0.1', '--server', UP)
for path, body, want in (('/gameapi/pollux/', pollux, '/api/pollux/'),
                         ('/purchasing/HappyTicketSum', tickets, '/api/HappyTicketSum'),
                         ('/telemetry/TelemetryEntity/?name=recordingsaveloadreport', telemetry,
                          '/api/TelemetryEntity/?name=recordingsaveloadreport')):
    seen.clear()
    status, headers, reply = post(port, path, body, CLIENT_HEADERS)
    got = seen[0] if seen else {}
    check(f'{path}: reaches gameapi at {want}', got.get('path') == want, got.get('path'))
    check(f'{path}: same body', got.get('body') == body)
    check(f'{path}: client headers kept', got.get('headers', {}).get('x-authorization') == 'XBL2.0 x='
          and got.get('headers', {}).get('x-xbl-contract-version') == '1')
    check(f'{path}: Host is gameapi', got.get('headers', {}).get('host') == UP.split('/')[2])
    check(f'{path}: gameapi reply sent back', status == 200 and json.loads(reply) == {'path': want, 'len': len(body)}
          and headers.get('X-Test') == 'yes', reply)

big = b'p' * 100000
seen.clear()
status, _, reply = post(port, '/gameapi/pollux/', big, CLIENT_HEADERS)
check('100 KB body forwarded whole', seen and seen[0]['body'] == big and json.loads(reply)['len'] == len(big))

status, _, reply = post(port, '/gameapi/missing', b'x')
check('gameapi 404 passed back', status == 404 and reply == b'{"error":"not here"}', (status, reply))
status, headers, _ = post(port, '/gameapi/redirect', b'x')
check('redirect passed back, not followed', status == 302 and headers.get('Location') == '/api/elsewhere', status)

seen.clear()
c = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
c.putrequest('POST', '/gameapi/pollux/')
c.putheader('Transfer-Encoding', 'chunked')
c.endheaders()
for part in (pollux[:20], pollux[20:]):
    c.send(b'%x\r\n%s\r\n' % (len(part), part))
c.send(b'0\r\n\r\n')
r = c.getresponse()
r.read()
check('chunked body forwarded', r.status == 200 and seen and seen[0]['body'] == pollux)
c.close()

c = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
ok = True
for _ in range(3):
    c.request('POST', '/gameapi/pollux/', body=pollux, headers=CLIENT_HEADERS)
    r = c.getresponse()
    ok = ok and r.status == 200 and json.loads(r.read())['len'] == len(pollux)
c.close()
check('three requests on one kept-alive connection', ok)

log = stop(p)
check('log shows the request', 'path: /gameapi/pollux/' in log and "body: b'version:Cores_EarlyAccess" in log)
check('log shows where it went and the reply', f'-> POST {UP}/pollux/' in log and 'sending 200: ' in log)
check('log shows long bodies cut', '(100000 bytes)' in log)

p, port = start('--host', '127.0.0.1', '--server', UP, '--local-telemetry')
seen.clear()
status, _, reply = post(port, '/telemetry/TelemetryEntity/?name=recordingrestapiresult', telemetry)
check('--local-telemetry: answered here, empty 200', status == 200 and reply == b'' and not seen)
status, _, _ = post(port, '/gameapi/pollux/', pollux)
check('--local-telemetry: pollux still forwarded', status == 200 and len(seen) == 1)
stop(p)

p, port = start('--host', '127.0.0.1', '--server', f'http://127.0.0.1:{free_port()}/api', '--timeout', '3')
status, _, reply = post(port, '/gameapi/pollux/', pollux)
check('gameapi down: 502', status == 502 and reply == b'', status)
check('gameapi down: logged', 'gameapi did not answer' in stop(p))

p, port = start('--server', UP)
status4 = post(port, '/pollux/', pollux)[0]
try:
    status6 = post(port, '/pollux/', pollux, host='::1')[0]
except OSError as e:
    status6 = f'no IPv6 here: {e}'
check('default listens on 127.0.0.1', status4 == 200, status4)
check('default listens on ::1', status6 == 200, status6)
stop(p)

r = subprocess.run([sys.executable, '-I', SCRIPT, '--server', 'gameapi.hwapi.live'], capture_output=True, text=True)
check('server without http(s): refused', r.returncode != 0)

up.shutdown()
shutil.rmtree(WORK, ignore_errors=True)
print('\n' + ('all checks passed' if not fails else f'{fails} checks failed'))
sys.exit(1 if fails else 0)
