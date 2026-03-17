#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to run this script."
  exit 1
fi

cd "${ROOT_DIR}"

python3 - <<'PY'
import pathlib
import re
import subprocess
import sys


COPYRIGHT_RE = re.compile(r"(\(c\)\s*)(\d{4})(?:-(\d{4}))?")
MAX_SCAN_LINES = 40


def run_git(args):
    result = subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result


def get_tracked_files():
    result = run_git(["ls-files"])
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(result.returncode)
    return [line for line in result.stdout.splitlines() if line]


def get_last_modified_year(path):
    result = run_git(["log", "-1", "--format=%ad", "--date=format:%Y", "--", path])
    year = result.stdout.strip()
    if result.returncode != 0 or not year or not year.isdigit():
        return None
    return int(year)


def update_copyright_line(line, last_year):
    match = COPYRIGHT_RE.search(line)
    if not match:
        return None

    start_year = int(match.group(2))
    # Keep the original first year unless it is invalidly newer than last_year.
    if start_year > last_year:
        start_year = last_year

    if start_year == last_year:
        year_text = f"{start_year}"
    else:
        year_text = f"{start_year}-{last_year}"

    new_line = f"{line[:match.start(2)]}{year_text}{line[match.end():]}"
    if new_line == line:
        return None
    return new_line


def process_file(path):
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False

    lines = text.splitlines(keepends=True)
    scan_limit = min(len(lines), MAX_SCAN_LINES)

    last_year = get_last_modified_year(path)
    if last_year is None:
        return False

    changed = False
    for i in range(scan_limit):
        if "Copyright" not in lines[i]:
            continue

        updated = update_copyright_line(lines[i], last_year)
        if updated is not None:
            lines[i] = updated
            changed = True
            break

    if changed:
        pathlib.Path(path).write_text("".join(lines), encoding="utf-8")
    return changed


def main():
    changed_files = []
    for tracked_file in get_tracked_files():
        if process_file(tracked_file):
            changed_files.append(tracked_file)

    if changed_files:
        print(f"Updated copyright years in {len(changed_files)} file(s):")
        for path in changed_files:
            print(f"  {path}")
    else:
        print("No copyright year updates were needed.")


if __name__ == "__main__":
    main()
PY
