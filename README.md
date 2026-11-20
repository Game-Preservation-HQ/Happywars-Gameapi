# HappyWarsGameapiPatch

A small script that points the Happy Wars PC client at the Happy Wars Revival gameapi server for everything: save data, game results, Happy Tickets, purchases, telemetry and sts.

The client has the old Microsoft server addresses (`*.happywarspc.msgamestudios.com`) built in, and those servers are gone. This script rewrites every copy of those addresses in `HappyWars.exe` and writes a patched copy. I made it for the Steam Early Access build (the one that sends `version:Cores_EarlyAccess`).

## Usage

You need Python 3. No extra packages. Put `patch.py` next to `HappyWars.exe` and run:

```
py patch.py
```

That writes `NewHappyWars.exe`. Other file names: `py patch.py in.exe out.exe`. To use your own gameapi instead: `py patch.py --server http://127.0.0.1:8080/api`.

The input file is never changed, but keep a backup of your exe anyway. The script prints every string it changes and every one it leaves alone.

## What gets rewritten

With the default server `https://gameapi.hwapi.live/api`:

| In the exe | Becomes |
|---|---|
| `https://gameapi.happywarspc.msgamestudios.com` | `https://gameapi.hwapi.live/api` |
| `https://gameapi.happywarspc.msgamestudios.com/api/pollux/` | `https://gameapi.hwapi.live/api/pollux/` |
| `https://sts.…`, `https://telemetry.…`, `https://purchasing.…` | `https://gameapi.hwapi.live/api` |
| `*.happywarspc.msgamestudios.com` (TLS name check) | `*.gameapi.hwapi.live` |
| `gameapi.happywarspc.msgamestudios.com` (bare host name) | `gameapi.hwapi.live` |

The client adds its own paths to these addresses (`/pollux/`, `/TelemetryEntity/`, `HappyTicketSum`, …). That's why the original path is kept and only moved under the server's `/api`. So a call to `/pollux/` ends up at `https://gameapi.hwapi.live/api/pollux/`.

## Notes

- Every copy of each address is patched, not only the first one.
- The addresses are zero-terminated strings inside the exe, so a new address has to fit in the old one's bytes. The rest is filled with zeros. If it doesn't fit, nothing is written; use a shorter `--server`.
- Nothing is written if the exe has no gameapi address at all.
- Strings that only mention the old domain inside other text (an error message, say) are listed and left alone. UTF-16 copies are reported but not patched.
- Telemetry and sts requests go to gameapi too.
- `--old-domain` lets you patch a build that uses a different old domain.

## Tests

```
py tests/test_patch.py
```

This builds a small fake exe with the same string layout, patches it and checks every string.

## Credits

Based on [kprotty's patch script](https://gist.github.com/kprotty/f09aa4b84e4f283575e697f22d07171a), which pointed the first copy of each address at a local server.

## License

Copyright (C) 2026 Serenity, Game Preservation HQ.

HappyWarsGameapiPatch is free software under the [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0-only). You may use, change and share it, on these conditions:

- **Credit:** every copy, and every changed version, must keep the copyright notice above and the credit to Serenity, together with the license.
- **Share the code:** if you give anyone a copy, or a changed version, you must also give them its full source code under this same license. This also applies when you run a changed version on a website or server that other people use: you must offer those people the source of your version.

The license comes with no warranty. The full terms are in [LICENSE](LICENSE).
