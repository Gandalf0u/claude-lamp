#!/usr/bin/env python3
"""
Moonside LED hook for Claude Code — cross-platform replacement for moonside_hook.sh.
Usage: moonside_hook.py <working|idle|input|off>
Always exits 0 to never block Claude.
"""

import os
import subprocess
import sys
import tempfile

_TMP = tempfile.gettempdir()
PID_FILE = os.path.join(_TMP, "moonside_daemon.pid")
STATE_FILE = os.path.join(_TMP, "moonside_state")
LOG_FILE = os.path.join(_TMP, "moonside_daemon.log")

DAEMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "moonside_daemon.py")


def _log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[moonside_hook] {msg}\n")
    except OSError:
        pass


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _find_python() -> str | None:
    """Return the first python executable that has bleak installed."""
    candidates = [sys.executable, "python3", "python"]

    # Add Homebrew and conda paths on Unix
    if sys.platform != "win32":
        candidates += ["/opt/homebrew/bin/python3"]
        conda = os.environ.get("CONDA_PREFIX")
        if conda:
            candidates.append(os.path.join(conda, "bin", "python3"))

    for exe in candidates:
        try:
            result = subprocess.run(
                [exe, "-c", "import bleak"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return exe
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def _launch_daemon(python: str) -> None:
    """Launch moonside_daemon.py as a detached background process."""
    with open(LOG_FILE, "a") as log_fp:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                [python, DAEMON],
                stdout=log_fp,
                stderr=log_fp,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                [python, DAEMON],
                stdout=log_fp,
                stderr=log_fp,
                start_new_session=True,
            )
    # Write the PID so subsequent hook calls can detect the running daemon
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(proc.pid))
    except OSError as e:
        _log(f"Could not write PID file: {e}")


def main() -> None:
    state = sys.argv[1] if len(sys.argv) > 1 else "idle"

    # 1. Write desired state
    try:
        with open(STATE_FILE, "w") as f:
            f.write(state)
    except OSError as e:
        _log(f"Could not write state file: {e}")

    # 2. If daemon is already alive, nothing more to do
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            if _is_running(pid):
                sys.exit(0)
        except (OSError, ValueError):
            pass
        # Stale PID file — remove it
        try:
            os.unlink(PID_FILE)
        except OSError:
            pass

    # 3. Auto-detect python with bleak
    python = _find_python()
    if python is None:
        _log("No python with bleak found, skipping")
        sys.exit(0)

    # 4. Launch daemon
    try:
        _launch_daemon(python)
    except Exception as e:
        _log(f"Failed to launch daemon: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
