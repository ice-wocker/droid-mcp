# droid-mcp 📱 — English

[![CI](https://github.com/ice-wocker/droid-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ice-wocker/droid-mcp/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/ice-wocker/droid-mcp?style=social)](https://github.com/ice-wocker/droid-mcp/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Your Android phone as MCP tools: 47 tools, 3 backends, 1 Python file, 0 dependencies.**

Give any MCP client (Claude Code / Claude Desktop / OpenCode) eyes and hands on
your phone: read SMS verification codes, check battery, push notifications,
take photos, read sensors, manage files — all on-device, no cloud.

⭐ Star us if useful! Full docs (Chinese, more detailed) live in [README.md](README.md).

## 30 seconds

On your phone: Termux + Termux:API (`pkg install termux-api`). Then:

```bash
git clone https://github.com/ice-wocker/droid-mcp.git && cd droid-mcp
claude mcp add droid-mcp -- python3 $(pwd)/droid_mcp.py
```

```
you: what's the verification code I just got by SMS?
AI: ● sms_inbox
    482916 (MockPay, valid 5 min). Want it in your clipboard?
```

No phone at hand? `python3 droid_mcp.py --mock` plays with fake data.
No Termux? Install the companion APK from
[Releases](https://github.com/ice-wocker/droid-mcp/releases) and use
`--backend companion --companion http://PHONE-IP:4833 --token XXX`.

## Three backends (auto-selected)

| backend | tools | when |
|---|---|---|
| `termux` | 47/47 | server runs in Termux on the phone |
| `companion` | 20/47 (all data tools) | companion APK, no Termux needed |
| `mock` | 47/47 fake data | demo / CI |

`--read-only` hides all 24 mutating tools. See the full 47×3 matrix in
[README.md](README.md#兼容矩阵核心) and per-tool reference in [docs/TOOLS.md](docs/TOOLS.md).

## More ways in

- **HTTP transport**: `python3 droid_mcp.py --mock --http 0.0.0.0:4844` →
  MCP over `POST /mcp`, health at `GET /health`. Phone in pocket, agent in cloud.
- **Web console**: `python3 console.py` → dashboard at
  `http://127.0.0.1:4855` (status, tool catalog, live call log, try tools online).
- **Agent skill**: [`skills/phone-assistant/SKILL.md`](skills/phone-assistant/SKILL.md)
  teaches your agent phone etiquette (2FA flow, spending ops, privacy red lines).

## Privacy & security in one paragraph

No servers, no cloud: SMS/contacts/location pass through your phone's memory
into your own AI session. Companion talks LAN-only with a per-device token.
SMS/calls are double-gated (in-app switches + client approvals). Storage is
jailed to /sdcard + home. Threat model (and what we explicitly DON'T cover):
[docs/SECURITY.md](docs/SECURITY.md).

## Dev

```bash
pip install pytest && pytest -q   # mock mode, no phone needed
```

Changelog: [CHANGELOG.md](CHANGELOG.md). Companion protocol: [docs/PROTOCOL.md](docs/PROTOCOL.md).
Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## License

MIT — see [LICENSE](LICENSE).
