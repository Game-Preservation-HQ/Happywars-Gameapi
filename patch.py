# Copyright (C) 2026 Serenity, Game Preservation HQ.
# SPDX-License-Identifier: AGPL-3.0-only

"""Point the Happy Wars client at the gameapi server for everything.

Every address of the old Microsoft servers (sts, telemetry, purchasing and gameapi
.happywarspc.msgamestudios.com) in HappyWars.exe is rewritten to the gameapi server,
so the client gets save data, game results, Happy Tickets, purchases, telemetry and
sts all from gameapi. Every copy of each address is patched, not only the first one.

    py patch.py                                   HappyWars.exe -> NewHappyWars.exe
    py patch.py in.exe out.exe
    py patch.py --server http://127.0.0.1:8080/api    (a local gameapi instead)

How an address is rewritten (server https://gameapi.hwapi.live/api):
    https://gameapi.happywarspc.msgamestudios.com             -> https://gameapi.hwapi.live/api
    https://gameapi.happywarspc.msgamestudios.com/api/pollux/ -> https://gameapi.hwapi.live/api/pollux/
    https://telemetry.happywarspc.msgamestudios.com/api       -> https://gameapi.hwapi.live/api
    *.happywarspc.msgamestudios.com  (TLS name check)         -> *.gameapi.hwapi.live
    gameapi.happywarspc.msgamestudios.com  (bare host name)   -> gameapi.hwapi.live
The client adds its own paths (/pollux/, /TelemetryEntity/, /HappyTicketSum, ...),
so the original path is kept and only moved under the server's /api.

The addresses are plain zero-terminated strings, so a new one has to fit in the old
one's bytes; the rest is filled with zeros. Strings that only mention the old domain
inside other text are reported and left alone. Nothing is written if a gameapi
address is missing or a new address does not fit.
"""
import argparse
import re
import sys
from urllib.parse import urlsplit

DEFAULT_SERVER = 'https://gameapi.hwapi.live/api'
OLD_DOMAIN = 'happywarspc.msgamestudios.com'
SERVICES = ('sts', 'telemetry', 'purchasing', 'gameapi')


def enclosing_string(data, pos):
    """Start and end (index of the terminating zero) of the printable string around pos."""
    start = pos
    while start > 0 and 0x20 <= data[start - 1] <= 0x7e:
        start -= 1
    end = pos
    while end < len(data) and 0x20 <= data[end] <= 0x7e:
        end += 1
    if end >= len(data) or data[end] != 0:
        return None  # not a zero-terminated string
    return start, end


def replacement(text, old_domain, server):
    """New text for one string, or None when it is not a plain address."""
    svc = '|'.join(SERVICES)
    dom = re.escape(old_domain)
    origin = f'{server.scheme}://{server.netloc}'
    base = server.path.rstrip('/')

    m = re.fullmatch(rf'https?://({svc})\.{dom}(?::\d+)?(/\S*)?', text)
    if m:
        path = m.group(2) or ''
        if base and (path == base or path.startswith(base + '/')):
            return m.group(1), origin + path
        return m.group(1), origin + base + path

    if text == f'*.{old_domain}':
        return 'tls-name', f'*.{server.hostname}'

    m = re.fullmatch(rf'({svc})\.{dom}', text)
    if m:
        return m.group(1), server.hostname

    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('input', nargs='?', default='HappyWars.exe')
    ap.add_argument('output', nargs='?', default='NewHappyWars.exe')
    ap.add_argument('--server', default=DEFAULT_SERVER,
                    help=f'gameapi base address (default {DEFAULT_SERVER})')
    ap.add_argument('--old-domain', default=OLD_DOMAIN,
                    help=f'domain to replace (default {OLD_DOMAIN})')
    args = ap.parse_args()

    server = urlsplit(args.server)
    if server.scheme not in ('http', 'https') or not server.hostname:
        sys.exit(f'--server must be an http(s) address, got {args.server!r}')
    if args.input == args.output:
        sys.exit('output must be a different file from input')

    with open(args.input, 'rb') as f:
        data = bytearray(f.read())

    needle = args.old_domain.encode()
    seen = set()
    changes = []   # (start, end, old, new, kind)
    skipped = []   # (start, text)
    too_long = []
    pos = data.find(needle)
    while pos != -1:
        span = enclosing_string(data, pos)
        if span and span not in seen:
            seen.add(span)
            start, end = span
            old = data[start:end].decode('ascii')
            rep = replacement(old, args.old_domain, server)
            if rep is None:
                skipped.append((start, old))
            elif len(rep[1]) > len(old):
                too_long.append((start, old, rep[1]))
            else:
                changes.append((start, end, old, rep[1], rep[0]))
        elif not span:
            skipped.append((pos, '(not a zero-terminated string)'))
        pos = data.find(needle, pos + 1)

    for start, end, old, new, kind in changes:
        print(f'0x{start:08X} [{kind}] {old}\n           -> {new}')
    for start, text in skipped:
        print(f'0x{start:08X} left as is: {text[:120]}')

    kinds = {kind for *_, kind in changes}
    for svc in SERVICES:
        if svc not in kinds:
            print(f'note: no {svc} address found')
    wide = data.count(args.old_domain.encode('utf-16-le'))
    if wide:
        print(f'note: {wide} UTF-16 copies of {args.old_domain} are not patched')

    if too_long:
        for start, old, new in too_long:
            print(f'0x{start:08X} does not fit ({len(new)} > {len(old)} bytes): {new}')
        sys.exit('nothing written: use a shorter --server')
    if 'gameapi' not in kinds:
        sys.exit(f'nothing written: no gameapi address found in {args.input}')

    for start, end, old, new, kind in changes:
        data[start:end] = new.encode('ascii').ljust(end - start, b'\x00')

    with open(args.output, 'wb') as f:
        f.write(data)
    print(f'\n{len(changes)} strings patched -> {args.output}')


if __name__ == '__main__':
    main()
