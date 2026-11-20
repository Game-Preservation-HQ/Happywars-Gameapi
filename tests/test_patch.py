# Copyright (C) 2026 Serenity, Game Preservation HQ.
# SPDX-License-Identifier: AGPL-3.0-only

"""Checks for patch.py on a small fake exe with the same string layout.

    py tests/test_patch.py
"""
import os
import random
import subprocess
import sys
import tempfile

PATCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patch.py')
D = 'happywarspc.msgamestudios.com'
fails = 0


def check(name, ok, extra=''):
    global fails
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({extra})' if extra and not ok else ''))
    fails += not ok


def cstr(data, off):
    return data[off:data.index(b'\0', off)].decode()


def run(work, *args):
    return subprocess.run([sys.executable, '-I', PATCH, *args], cwd=work, capture_output=True, text=True)


# (original string, expected with the default server, expected with a local server)
CASES = [
    (f'https://gameapi.{D}', 'https://gameapi.hwapi.live/api', 'http://127.0.0.1:8080/api'),
    (f'https://gameapi.{D}/api/pollux/', 'https://gameapi.hwapi.live/api/pollux/', 'http://127.0.0.1:8080/api/pollux/'),
    (f'https://sts.{D}', 'https://gameapi.hwapi.live/api', 'http://127.0.0.1:8080/api'),
    (f'https://telemetry.{D}/api', 'https://gameapi.hwapi.live/api', 'http://127.0.0.1:8080/api'),
    (f'https://purchasing.{D}', 'https://gameapi.hwapi.live/api', 'http://127.0.0.1:8080/api'),
    (f'*.{D}', '*.gameapi.hwapi.live', '*.127.0.0.1'),
    (f'gameapi.{D}', 'gameapi.hwapi.live', '127.0.0.1'),
    (f'Could not reach https://gameapi.{D}', None, None),  # text: left alone
    (f'https://gameapi.{D}', 'https://gameapi.hwapi.live/api', 'http://127.0.0.1:8080/api'),  # second copy
]

with tempfile.TemporaryDirectory() as work:
    random.seed(1)
    blob = bytearray()
    offs = []
    for s, _, _ in CASES:
        blob += bytes(random.randrange(1, 256) for _ in range(37)) + b'\0' * 3
        offs.append(len(blob))
        blob += s.encode() + b'\0' * (4 - len(s) % 4)
    blob += ('x' + D).encode('utf-16-le') + b'\0\0' + bytes(random.randrange(256) for _ in range(64))
    with open(os.path.join(work, 'HappyWars.exe'), 'wb') as f:
        f.write(blob)

    for label, args, col in (('default server', (), 1),
                             ('local server', ('HappyWars.exe', 'local.exe', '--server', 'http://127.0.0.1:8080/api'), 2)):
        r = run(work, *args)
        check(f'{label}: exits 0', r.returncode == 0, r.stderr.strip())
        out = open(os.path.join(work, args[1] if args else 'NewHappyWars.exe'), 'rb').read()
        check(f'{label}: same size', len(out) == len(blob))
        for off, case in zip(offs, CASES):
            want = case[col] or case[0]
            check(f'{label}: {case[0][:48]!r}', cstr(out, off) == want, cstr(out, off))
        changed = [i for i in range(len(blob)) if blob[i] != out[i]]
        check(f'{label}: only the patched strings changed',
              all(any(o <= i < o + len(c[0]) for o, c in zip(offs, CASES)) for i in changed))
    check('UTF-16 copy reported', 'UTF-16' in r.stdout)

    r = run(work, 'HappyWars.exe', 'long.exe', '--server', 'https://a-very-long-host-name.example.org/api/v1/game')
    check('server too long: fails', r.returncode != 0)
    check('server too long: nothing written', not os.path.exists(os.path.join(work, 'long.exe')))

    r = run(work, 'HappyWars.exe', 'HappyWars.exe')
    check('same input and output: refused', r.returncode != 0)

    with open(os.path.join(work, 'empty.exe'), 'wb') as f:
        f.write(b'\0' * 64)
    r = run(work, 'empty.exe', 'empty_new.exe')
    check('no gameapi address: fails, nothing written',
          r.returncode != 0 and not os.path.exists(os.path.join(work, 'empty_new.exe')))

print('\n' + ('all checks passed' if not fails else f'{fails} checks failed'))
sys.exit(1 if fails else 0)
