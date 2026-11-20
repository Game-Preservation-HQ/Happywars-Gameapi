# Copyright (C) 2026 Serenity, Game Preservation HQ.
# SPDX-License-Identifier: AGPL-3.0-only

"""Local Happy Wars server that gets everything from gameapi.

The client patched by the original gist's patch.py sends every request to
http://localhost:12345/<service>. This server takes each one, forwards it to the
gameapi server and sends gameapi's reply back to the client, so save data, game
results, Happy Tickets, purchases, telemetry and sts all come from gameapi. Every
request and reply is printed, like the old capture log.

    py HappyWars.py                                   localhost:12345 -> https://gameapi.hwapi.live/api
    py HappyWars.py --server http://127.0.0.1:8099/api   (a local gameapi instead)
    py HappyWars.py --log capture.txt                 also append the log to a file

Where a request goes (server https://gameapi.hwapi.live/api):
    /gameapi/pollux/                      -> https://gameapi.hwapi.live/api/pollux/
    /pollux/                              -> https://gameapi.hwapi.live/api/pollux/
    /purchasing/HappyTicketSum            -> https://gameapi.hwapi.live/api/HappyTicketSum
    /telemetry/TelemetryEntity/?name=...  -> https://gameapi.hwapi.live/api/TelemetryEntity/?name=...
    /api/pollux/                          -> https://gameapi.hwapi.live/api/pollux/
The service prefix the patch added (/gameapi, /telemetry, /purchasing, /sts) and the
server's own base path (/api) are dropped, and the rest goes under the server's address.
A client patched with this repo's patch.py and --server http://localhost:12345/api
works too.

What the Steam Early Access client sends (from the gist's capture; <steamid> is the
player's Steam id). The pollux bodies are version:Cores_EarlyAccess,f:<function>,
userid:(null),pid:<steamid>,xuid:DEBUG_CLIENT_XUID,... The quick match requests in the
capture have the /gameapi or /telemetry prefix the gist's patch adds; the earlier ones
have none, probably from an older version of the patch.
    Press Start    POST /pollux/                 f:CoreSaveDataLoad
                   POST /TelemetryEntity/?name=recordingsaveloadreport
    Play           POST /HappyTicketSum          {"steamid":<steamid>,"appid":246280}
    Happy Cards    POST /HappyTicketAsset        {"steamid":<steamid>,"appid":246280}
    Skirmish end   POST /pollux/                 f:GameResult
                   POST /TelemetryEntity/?name=recordingplayergameresult
    Quick match    POST /gameapi/pollux/         f:LoadingGameStart (g_det_mode:4)
                   POST /telemetry/TelemetryEntity/?name=recordingmatchingresultcollection
    Match end      POST /gameapi/pollux/         f:GameResult
                   POST /telemetry/TelemetryEntity/?name=recordingplayergameresult
                   POST /telemetry/TelemetryEntity/?name=recordingrestapiresult
"""
import argparse
import re
import socket
import socketserver
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

DEFAULT_SERVER = 'https://gameapi.hwapi.live/api'
SERVICE_PREFIX = re.compile(r'/(?:gameapi|telemetry|purchasing|sts)(?=/|\?|[A-Z]|$)')
HOP_BY_HOP = {'connection', 'keep-alive', 'proxy-connection', 'proxy-authenticate',
              'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade',
              'host', 'content-length', 'accept-encoding', 'expect'}


def upstream_url(server, raw_path):
    """The gameapi address for a path the client asked for."""
    path, sep, query = raw_path.partition('?')
    m = SERVICE_PREFIX.match(path)
    if m:
        path = path[m.end():]
    if not path.startswith('/'):
        path = '/' + path
    base = urlsplit(server).path.rstrip('/')
    if base and (path == base or path.startswith(base + '/')):
        path = path[len(base):] or '/'
    return server.rstrip('/') + path + sep + query


def shown(data, limit):
    if limit and len(data) > limit:
        return f'{data[:limit]!r} ... ({len(data)} bytes)'
    return repr(data)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand redirects back to the client instead of following them (a POST would lose its body)."""
    def redirect_request(self, *args, **kwargs):
        return None


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    opts = None
    opener = urllib.request.build_opener(NoRedirect)
    log_lock = threading.Lock()

    def log_message(self, *args):
        pass  # the log below replaces the default one

    def read_body(self):
        if 'chunked' in self.headers.get('Transfer-Encoding', '').lower():
            data = b''
            while True:
                size = int(self.rfile.readline().split(b';')[0].strip() or b'0', 16)
                if size == 0:
                    while self.rfile.readline() not in (b'\r\n', b'\n', b''):
                        pass
                    return data
                data += self.rfile.read(size)
                self.rfile.readline()
        length = int(self.headers.get('Content-Length') or 0)
        return self.rfile.read(length) if length > 0 else b''

    def forward(self):
        opts = self.opts
        body = self.read_body()
        url = upstream_url(opts.server, self.path)
        lines = [f'method: {self.command}', f'path: {self.path}']
        if body:
            lines.append(f'body: {shown(body, opts.log_bytes)}')
        lines.append('headers: {' + ', '.join(f'{k!r}: {v!r}' for k, v in self.headers.items()) + '}')

        headers = []
        if opts.local_telemetry and urlsplit(url).path.startswith(
                urlsplit(opts.server).path.rstrip('/') + '/TelemetryEntity'):
            status, headers, reply = 200, [('Content-Type', 'text/plain')], b''
            lines.append('answered here (--local-telemetry)')
        else:
            lines.append(f'-> {self.command} {url}')
            fwd = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
            req = urllib.request.Request(url, data=body if self.command != 'GET' else None,
                                         headers=fwd, method=self.command)
            try:
                with self.opener.open(req, timeout=opts.timeout) as r:
                    status, headers, reply = r.status, r.getheaders(), r.read()
            except urllib.error.HTTPError as e:
                status, headers, reply = e.code, list(e.headers.items()), e.read()
            except (urllib.error.URLError, OSError) as e:
                status, headers, reply = 502, [('Content-Type', 'text/plain')], b''
                lines.append(f'gameapi did not answer: {getattr(e, "reason", e)}')

        self.send_response(status)
        for k, v in headers:
            if k.lower() not in HOP_BY_HOP:
                self.send_header(k, v)
        self.send_header('Content-Length', str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

        lines.append(f'sending {status}: {shown(reply, opts.log_bytes)}')
        entry = '\n'.join(lines) + '\n'
        with self.log_lock:
            print(entry, flush=True)
            if opts.log:
                with open(opts.log, 'a', encoding='utf-8') as f:
                    f.write(entry + '\n')

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = forward


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)  # skips the slow reverse lookup HTTPServer does
        self.server_name, self.server_port = self.server_address[:2]


class Server6(Server):
    address_family = socket.AF_INET6


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--server', default=DEFAULT_SERVER,
                    help=f'gameapi base address (default {DEFAULT_SERVER})')
    ap.add_argument('--host', default='localhost',
                    help='address to listen on (default localhost: 127.0.0.1 and ::1)')
    ap.add_argument('--port', type=int, default=12345, help='port to listen on (default 12345)')
    ap.add_argument('--log', help='also append the log to this file')
    ap.add_argument('--log-bytes', type=int, default=2000,
                    help='longest body shown in the log, 0 = all (default 2000)')
    ap.add_argument('--timeout', type=float, default=30, help='seconds to wait for gameapi (default 30)')
    ap.add_argument('--local-telemetry', action='store_true',
                    help='answer TelemetryEntity requests here with an empty 200 instead of forwarding them')
    opts = ap.parse_args()

    server = urlsplit(opts.server)
    if server.scheme not in ('http', 'https') or not server.hostname:
        sys.exit(f'--server must be an http(s) address, got {opts.server!r}')
    Handler.opts = opts
    sys.stdout.reconfigure(errors='backslashreplace')

    hosts = ['127.0.0.1', '::1'] if opts.host == 'localhost' else [opts.host]
    servers = []
    for host in hosts:
        cls = Server6 if ':' in host else Server
        try:
            servers.append(cls((host, opts.port), Handler))
        except OSError as e:
            print(f'note: cannot listen on [{host}]:{opts.port}: {e}')
    if not servers:
        sys.exit('nothing to listen on')

    for s in servers[1:]:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    where = ', '.join(f'[{s.server_name}]:{s.server_port}' for s in servers)
    print(f'listening on {where}, forwarding to {opts.server}\n', flush=True)
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for s in servers:
            s.server_close()


if __name__ == '__main__':
    main()
