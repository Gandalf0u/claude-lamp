# Claude Lamp

Control your [Moonside](https://moonside.design) LED lamp via BLE based on Claude Code's state. Your lamp becomes a physical status indicator — animated themes while Claude works, green when idle, purple when it needs your input.

> **WARNING** Author takes no responsibility for the hardware issues that may arise from using this script. You run these scripts at your own risk.

**NOTE** The initial connection handshake with the lamp might take few seconds, please tail the daemon logs to check it all works fine.

## Demo

| State | Lamp | Trigger |
|---|---|---|
| **Working** | BEAT2 theme (white/navy) | Prompt submit, tool use |
| **Idle** | Solid sunset mango | Claude finishes responding, session start |
| **Needs input** | Solid purple | Permission request, plan approval, question, notification |
| **Off** | LED off | Session end |

## Requirements

- macOS or Windows (BLE via CoreBluetooth / WinRT)
- Python 3.10+
- [bleak](https://github.com/hbldh/bleak) (`pip install bleak`)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- A Moonside lamp (tested with Halo — should work with One, Aurora, Lighthouse etc.)

## Windows

`moonside_hook.py` is a cross-platform Python replacement for `moonside_hook.sh`. On Windows, use it together with `settings_windows.json` instead of the `.sh` / `settings.json` pair.

### Windows setup

#### 1. Install bleak

```powershell
pip install bleak
```

#### 2. Copy scripts

```powershell
mkdir "$env:USERPROFILE\.claude\moonside_hooks" -Force
Copy-Item claude_hooks\moonside_hook.py, claude_hooks\moonside_daemon.py "$env:USERPROFILE\.claude\moonside_hooks\"
```

No `chmod` needed on Windows.

#### 3. Install the hooks

Merge `claude_hooks/settings_windows.json` into `%USERPROFILE%\.claude\settings.json`. Replace `$CLAUDE_PROJECT_DIR/claude_hooks` with the path you copied the scripts to (e.g. `%USERPROFILE%\.claude\moonside_hooks`).

#### 4. Restart Claude Code

Open a new Claude Code session. The daemon will auto-discover your lamp by name.

> **Logs, PID and state files** are stored in `%TEMP%` (i.e. `C:\Users\<you>\AppData\Local\Temp\`) instead of `/tmp/` on macOS/Linux.

## Setup

### 1. Install bleak

```sh
pip install bleak
```

### 2. Copy scripts

```sh
mkdir -p ~/.claude/moonside_hooks
cp claude_hooks/moonside_hook.sh claude_hooks/moonside_daemon.py ~/.claude/moonside_hooks/
chmod +x ~/.claude/moonside_hooks/moonside_hook.sh
```

Putting them in `~/.claude/moonside_hooks/` means they work across all projects — no need to have `claude_hooks/` in every repo.

### 3. Install the hooks

Merge `claude_hooks/settings.json` into `~/.claude/settings.json`. The paths in the config use `$CLAUDE_PROJECT_DIR` — update them to point to `~/.claude/moonside_hooks/` instead:

```sh
sed 's|\$CLAUDE_PROJECT_DIR/claude_hooks|~/.claude/moonside_hooks|g' \
  claude_hooks/settings.json
```

Or just copy the JSON and replace the paths manually. The config hooks into `SessionStart`, `UserPromptSubmit`, `Stop`, `PreToolUse` (all tools), `PostToolUse`, `PermissionRequest`, `Notification`, and `SessionEnd`.

The daemon includes a debounce to prevent phantom working transitions (e.g. internal prompt suggestions firing PreToolUse shortly after Stop).

### 4. Restart Claude Code

Open a new Claude Code session. The daemon auto-discovers your lamp by name — no address configuration needed.

> **Multiple lamps?** Set `MOONSIDE_MAC` to pin a specific device. Run `python3 moonside_ble.py scan` to list devices. On macOS, addresses are UUIDs (not MAC addresses).

## Architecture

```
Claude Code hook event
  → moonside_hook.sh / moonside_hook.py (writes state to temp dir, launches daemon if needed)
    → moonside_daemon.py (persistent BLE connection, reads state file every 200ms)
      → Moonside lamp via BLE (Nordic UART Service)
```

The daemon keeps a persistent BLE connection to avoid 2-5s reconnect latency on every hook event. It runs in the background and auto-exits after 30 minutes of idle or on `SessionEnd`.

### Files

| File | Purpose |
|---|---|
| `claude_hooks/moonside_hook.sh` | Shell hook (macOS/Linux). Writes state, starts daemon if needed. Always exits 0. |
| `claude_hooks/moonside_hook.py` | Python hook (cross-platform, Windows). Same behaviour as the `.sh`. |
| `claude_hooks/moonside_daemon.py` | Background daemon with persistent BLE connection, state machine, and idle→working debounce. |
| `claude_hooks/settings.json` | Ready-to-use Claude Code hooks config for macOS/Linux. |
| `claude_hooks/settings_windows.json` | Ready-to-use Claude Code hooks config for Windows (uses `python` + `.py`). |
| `moonside_ble.py` | Standalone BLE controller for Moonside lamps. Usable directly from the command line. |

### Daemon lifecycle

- **PID file:** `<tempdir>/moonside_daemon.pid` (e.g. `/tmp/` on macOS/Linux, `%TEMP%` on Windows)
- **State file:** `<tempdir>/moonside_state`
- **Log file:** `<tempdir>/moonside_daemon.log`

## Standalone BLE controller

`moonside_ble.py` can be used independently of Claude Code:

```sh
python3 moonside_ble.py scan                     # find devices
python3 moonside_ble.py on                        # turn on
python3 moonside_ble.py off                       # turn off
python3 moonside_ble.py color 255 0 128           # set color
python3 moonside_ble.py color 255 0 128 --brightness 80
python3 moonside_ble.py theme rainbow3            # activate theme
python3 moonside_ble.py theme fire2 --colors 255,50,0
python3 moonside_ble.py raw "THEME.GRADIENT1.255,0,0,0,0,255"
python3 moonside_ble.py interactive               # REPL mode
```

## Troubleshooting

**Lamp not responding:**
```sh
# Check daemon log (macOS/Linux)
cat /tmp/moonside_daemon.log

# Windows (PowerShell)
Get-Content "$env:TEMP\moonside_daemon.log"

# Verify BLE connection works
python3 moonside_ble.py on
```

**Daemon stuck:**
```sh
# macOS/Linux
kill "$(cat /tmp/moonside_daemon.pid)"
rm -f /tmp/moonside_daemon.pid /tmp/moonside_state
```
```powershell
# Windows
Stop-Process -Id (Get-Content "$env:TEMP\moonside_daemon.pid")
Remove-Item "$env:TEMP\moonside_daemon.pid", "$env:TEMP\moonside_state"
```

**bleak not found:**
The hook auto-detects python from `python3`, `/opt/homebrew/bin/python3`, and `$CONDA_PREFIX/bin/python3`. Make sure one of them has bleak installed.

## Default colors

| State | Visual |
|---|---|
| Working | BEAT2 theme (white + navy) |
| Idle | Solid sunset mango (255, 180, 50) |
| Input | Solid purple (200, 0, 255) |

Colors are configured in `moonside_daemon.py`.

## Protocol

Moonside lamps use the Nordic UART Service (NUS) over BLE. Commands are ASCII text:

| Command | Format | Example |
|---|---|---|
| LED on/off | `LEDON` / `LEDOFF` | `LEDOFF` |
| Color (0-255) | `COLORRRRGGGBBB` | `COLOR000255000` |
| Brightness (0-120) | `BRIGHBBB` | `BRIGH060` |
| Theme | `THEME.NAME.R,G,B,...` | `THEME.FIRE2.255,50,0` |

## License

MIT

## Acknowledgments

- [HomeAssistant](https://community.home-assistant.io/t/integrating-moonside-t1-lighthouse/473578/8)
- [TheGreyDiamond](https://thegreydiamond.de/blog/2022/10/10/reverse-engineering-moonside-lighthouse/)
