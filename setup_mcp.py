"""Connect BRM Territory Hub to Claude Desktop.

Works out the right absolute paths for this computer and writes them into
Claude Desktop's config file. Existing entries in that file are preserved --
anything else you have connected keeps working, and the old file is backed up
first.

Run it by double-clicking setup_mcp.bat (Windows) or: python setup_mcp.py
"""
import json
import os
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SERVER_NAME = "brm-territory"


def claude_config_path():
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA")
        if not base:
            return None
        return Path(base) / "Claude" / "claude_desktop_config.json"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def python_executable():
    """Prefer the project's own virtual environment, so dependencies match."""
    if platform.system() == "Windows":
        venv = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        venv = PROJECT_DIR / ".venv" / "bin" / "python"
    if venv.exists():
        return str(venv)
    return sys.executable


def main():
    print("BRM Territory Hub -- Claude Desktop setup")
    print("=" * 55)

    server_script = PROJECT_DIR / "mcp_server.py"
    if not server_script.exists():
        print(f"ERROR: can't find {server_script}")
        print("Run this from inside the Territory Management folder.")
        return 1

    config_path = claude_config_path()
    if config_path is None:
        print("ERROR: couldn't work out where Claude Desktop keeps its settings.")
        return 1

    py = python_executable()
    print(f"Python:      {py}")
    print(f"Server:      {server_script}")
    print(f"Config file: {config_path}")
    print()

    config = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                config = json.loads(content) if content else {}
        except json.JSONDecodeError:
            print("WARNING: the existing config file isn't valid JSON.")
            print("It will be backed up and replaced with a fresh one.")
            config = {}
        backup = config_path.with_suffix(f".backup-{datetime.now():%Y%m%d-%H%M%S}.json")
        shutil.copy2(config_path, backup)
        print(f"Backed up existing config to:\n  {backup}\n")
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)

    servers = config.setdefault("mcpServers", {})
    already = SERVER_NAME in servers
    servers[SERVER_NAME] = {"command": py, "args": [str(server_script)]}

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    others = [k for k in servers if k != SERVER_NAME]
    print(f"{'Updated' if already else 'Added'} the '{SERVER_NAME}' connection.")
    if others:
        print(f"Left your other connections alone: {', '.join(others)}")
    print()
    print("DONE. Next steps:")
    print("  1. Quit Claude Desktop completely (not just the window --")
    print("     right-click the taskbar icon and Quit, or use Task Manager).")
    print("  2. Open Claude Desktop again.")
    print("  3. Ask it something like:")
    print('       "Using my territory data, who should I go see in Norfolk this week?"')
    print()
    print("Your data stays on this computer. Claude only receives the answer to")
    print("the specific question you ask -- never the whole database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
