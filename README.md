# Happywars-Gameapi

Two small scripts that point the Happy Wars PC client at the Happy Wars Revival gameapi server for everything: save data, game results, Happy Tickets, purchases, telemetry and sts.

The client has the old Microsoft server addresses (`*.happywarspc.msgamestudios.com`) built in, and those servers are gone. There are two ways to send the client to gameapi:

- `patch.py` rewrites every copy of those addresses in `HappyWars.exe` and writes a patched copy, so the client talks to gameapi directly.
- `HappyWars.py` is a small local server. A client patched to `http://localhost:12345` (the way the original gist's patch did it) sends its requests there. The server forwards each one to gameapi and sends gameapi's reply back, and it prints every request and reply.

I made them for the Steam Early Access build (the one that sends `version:Cores_EarlyAccess`).

## Patching the exe (patch.py)

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

## Local server (HappyWars.py)

```
py HappyWars.py
```

That listens on `localhost:12345` (both `127.0.0.1` and `::1`) and forwards to `https://gameapi.hwapi.live/api`. Other options: `--server http://127.0.0.1:8099/api` for your own gameapi, `--port`, `--host`, `--log capture.txt` to also write the log to a file, `--log-bytes 0` to show whole bodies.

| The client asks for | Goes to |
|---|---|
| `/gameapi/pollux/` or `/pollux/` | `https://gameapi.hwapi.live/api/pollux/` |
| `/purchasing/HappyTicketSum` or `/HappyTicketSum` | `https://gameapi.hwapi.live/api/HappyTicketSum` |
| `/telemetry/TelemetryEntity/?name=...` | `https://gameapi.hwapi.live/api/TelemetryEntity/?name=...` |
| `/api/...` | `https://gameapi.hwapi.live/api/...` |

The service prefix the patch added (`/gameapi`, `/telemetry`, `/purchasing`, `/sts`) and the server's own `/api` are dropped, and the rest goes under the server's address. So a client patched with `py patch.py --server http://localhost:12345/api` works with it too.

- The request body and the client's headers go to gameapi unchanged. gameapi's status, headers and body come back unchanged, and redirects are passed back rather than followed.
- If gameapi can't be reached, the client gets an empty `502`.
- A gameapi without a `TelemetryEntity` handler answers telemetry with `404`. `--local-telemetry` answers those requests locally with an empty `200` instead, the way the old capture server did.
- The log has the player's Steam id in it. Don't post it as is.

## Save data

[docs/SAVE-SYSTEM.md](docs/SAVE-SYSTEM.md) explains the save data the game loads at start-up (`JsonSaveData`): how the answer is packed, every member, the bit sets, character looks, items, the battle record and the options, with examples.

- [docs/save-example.json](docs/save-example.json) is a whole sample save in the form the game reads.
- [docs/save-example.txt](docs/save-example.txt) is the same save packed the way `CoreSaveDataLoad` sends it, for trying the unpacking code in the doc.

## Tests

```
py tests/test_patch.py
py tests/test_server.py
```

`test_patch.py` builds a small fake exe with the same string layout, patches it and checks every string. `test_server.py` runs `HappyWars.py` in front of a fake gameapi and checks where each request goes and what comes back.

## Credits

Based on [kprotty's gist](https://gist.github.com/kprotty/f09aa4b84e4f283575e697f22d07171a). Its `patch.py` pointed the first copy of each address at a local server, and its `HappyWars.py` was a log of what that server received.

## License

Copyright (C) 2026 Serenity, Game Preservation HQ.

Happywars-Gameapi is free software under the [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0-only). You may use, change and share it, on these conditions:

- **Credit:** every copy, and every changed version, must keep the copyright notice above and the credit to Serenity, together with the license.
- **Share the code:** if you give anyone a copy, or a changed version, you must also give them its full source code under this same license. This also applies when you run a changed version on a website or server that other people use: you must offer those people the source of your version.

The license comes with no warranty. The full terms are in [LICENSE](LICENSE).
