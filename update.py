"""Update BRM Territory Hub to the latest version.

Downloads the current code from GitHub and replaces the program files on this
computer. Your data is never touched: the `data` folder (database, imports,
backups) is explicitly excluded, and the database is backed up before anything
is copied.

Run it by double-clicking update.bat, or:
    python update.py
    python update.py --zip C:\\path\\to\\downloaded.zip   (offline / manual fallback)
"""
import argparse
import io
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

REPO = "Nbitzer445/Territory-Management"
BRANCH = "claude/gifted-hopper-o2r0cl"
ZIP_URL = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"

# Program files that get replaced on update.
CODE_ITEMS = [
    "app.py",
    "mcp_server.py",
    "setup_mcp.py",
    "setup_mcp.bat",
    "update.py",
    "update.bat",
    "run.sh",
    "run.bat",
    "backup.sh",
    "backup.bat",
    "requirements.txt",
    "README.md",
    "brm",
    "templates",
    "static",
]

# Never overwritten, whatever arrives in the download.
PROTECTED = {"data", ".venv", ".git"}


def download_zip():
    print(f"Downloading the latest version...\n  {ZIP_URL}")
    req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "BRM-Territory-Hub-Updater"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    print(f"  downloaded {len(data) / 1024:.0f} KB")
    return zipfile.ZipFile(io.BytesIO(data))


def open_local_zip(path):
    print(f"Using local file: {path}")
    return zipfile.ZipFile(path)


def extract_to_temp(zf, tmpdir):
    zf.extractall(tmpdir)
    entries = [p for p in Path(tmpdir).iterdir() if p.is_dir()]
    if len(entries) == 1:
        return entries[0]  # GitHub wraps everything in one folder
    return Path(tmpdir)


def backup_database():
    db = PROJECT_DIR / "data" / "territory.db"
    if not db.exists():
        return None
    backups = PROJECT_DIR / "data" / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    dest = backups / f"territory-before-update-{datetime.now():%Y%m%d-%H%M%S}.db"
    shutil.copy2(db, dest)
    return dest


def backup_code():
    dest = PROJECT_DIR / "data" / "code_backups" / f"{datetime.now():%Y%m%d-%H%M%S}"
    dest.mkdir(parents=True, exist_ok=True)
    for item in CODE_ITEMS:
        src = PROJECT_DIR / item
        if not src.exists():
            continue
        target = dest / item
        if src.is_dir():
            shutil.copytree(src, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    return dest


def apply_update(source_dir):
    changed, added = [], []
    for item in CODE_ITEMS:
        src = source_dir / item
        if not src.exists():
            continue
        if item in PROTECTED:
            continue
        dst = PROJECT_DIR / item
        existed = dst.exists()
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        (changed if existed else added).append(item)
    return changed, added


def main():
    parser = argparse.ArgumentParser(description="Update BRM Territory Hub")
    parser.add_argument("--zip", help="Use an already-downloaded zip instead of fetching it")
    args = parser.parse_args()

    print("BRM Territory Hub -- update")
    print("=" * 55)
    print(f"Folder: {PROJECT_DIR}\n")

    try:
        zf = open_local_zip(args.zip) if args.zip else download_zip()
    except Exception as e:
        print(f"\nCouldn't get the update: {e}")
        print("\nCheck your internet connection and try again. If it keeps failing,")
        print("download the zip from GitHub by hand and run:")
        print("    python update.py --zip C:\\path\\to\\the.zip")
        return 1

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            source = extract_to_temp(zf, tmpdir)
        except Exception as e:
            print(f"\nThe download looks damaged and wasn't applied: {e}")
            return 1

        # Only proceed if this really is the app -- never unpack junk over it.
        required = ["app.py", "brm", "templates"]
        missing = [r for r in required if not (source / r).exists()]
        if missing:
            print(f"\nThat file doesn't look like BRM Territory Hub (missing {', '.join(missing)}).")
            print("Nothing was changed.")
            return 1

        db_backup = backup_database()
        if db_backup:
            print(f"Database backed up to:\n  {db_backup}")
        code_backup = backup_code()
        print(f"Previous program files saved to:\n  {code_backup}\n")

        try:
            changed, added = apply_update(source)
        except Exception as e:
            print(f"\nUpdate failed partway through: {e}")
            print(f"Your previous program files are in:\n  {code_backup}")
            print("Your data was not touched.")
            return 1

    print("Updated:")
    for item in sorted(changed):
        print(f"  {item}")
    for item in sorted(added):
        print(f"  {item}  (new)")

    print("\nYour data folder was not touched -- accounts, calls, contacts,")
    print("follow-ups, groups and notes are all exactly as you left them.")
    print("\nDONE.")
    print("  If the app is running, it restarts itself within a few seconds --")
    print("  just refresh your browser at http://127.0.0.1:5000")
    print("  If it isn't running, start it with run.bat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
