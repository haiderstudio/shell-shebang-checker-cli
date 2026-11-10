#!/usr/bin/env python3
"""Check shell scripts start with a valid shebang line.

A script with no shebang runs under the wrong shell (or not at all)
when executed directly. This tool reports every script that is
missing a shebang, has one that is not on line 1, or names an
interpreter that does not exist on this machine, with the file and
line number, and exits 1 when any problem is found, so it can fail
a CI run. Report-only: it never rewrites a file.
"""

import argparse
import fnmatch
import json
import os
import shutil
import sys
from pathlib import Path

VERSION = "1.0.0"
SHELL_EXTENSIONS = {".sh"}


class Problem:
    """One problem found in one file."""

    def __init__(self, path, lineno, reason):
        self.path = path
        self.lineno = lineno
        self.reason = reason

    def line(self):
        """The human-readable report line for this problem."""
        return "FAIL %s:%d: %s" % (self.path, self.lineno, self.reason)

    def as_dict(self):
        """The JSON form of this problem."""
        return {"line": self.lineno, "reason": self.reason}


def check_shebang_line(line, path, lineno):
    """Check one line that starts with ``#!``.

    Returns a list of problems (empty when the shebang is valid).
    A valid shebang names an interpreter that exists on this
    machine and can be executed. ``#!/usr/bin/env NAME`` checks
    that NAME is on PATH instead.
    """
    rest = line[2:].strip()
    if not rest:
        return [Problem(path, lineno, "empty shebang (no interpreter after #!)")]
    parts = rest.split()
    interp = parts[0]
    if interp == "/usr/bin/env" or interp.endswith("/env"):
        if not os.path.exists(interp):
            return [Problem(path, lineno, "interpreter not found: %s" % interp)]
        program = None
        for token in parts[1:]:
            if token.startswith("-"):
                continue
            program = token
            break
        if program is None:
            return [Problem(path, lineno, "no program after /usr/bin/env")]
        if shutil.which(program) is None:
            return [Problem(path, lineno, "interpreter not found: %s" % program)]
        return []
    if not interp.startswith("/"):
        return [
            Problem(
                path,
                lineno,
                "interpreter is not an absolute path: %s" % interp,
            )
        ]
    if not os.path.exists(interp):
        return [Problem(path, lineno, "interpreter not found: %s" % interp)]
    if not os.access(interp, os.X_OK):
        return [Problem(path, lineno, "interpreter not executable: %s" % interp)]
    return []


def check_content(content, display_name):
    """Check the text of one script. Returns a list of problems."""
    lines = content.splitlines()
    if not lines:
        return [Problem(display_name, 1, "missing shebang")]
    first = lines[0]
    if first.startswith("#!"):
        return check_shebang_line(first, display_name, 1)
    for lineno, line in enumerate(lines[1:], start=2):
        if line.startswith("#!"):
            return [
                Problem(
                    display_name,
                    lineno,
                    "shebang must be on line 1, found on line %d" % lineno,
                )
            ]
    return [Problem(display_name, 1, "missing shebang")]


def check_file(path):
    """Check one file on disk. Returns a list of problems."""
    display = str(path)
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [Problem(display, 1, "cannot read file (not valid UTF-8)")]
    except OSError as exc:
        return [Problem(display, 1, "cannot read file (%s)" % exc.strerror)]
    return check_content(content, display)


def collect_files(paths, recursive, excludes):
    """Expand command-line paths into the files to check.

    A file given directly is always checked, whatever its name.
    A folder is walked for ``.sh`` files. Returns (files, error):
    files is a sorted list of Paths, error is a message string or
    None when everything is fine.
    """
    seen = set()
    found = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            return [], "no such file or directory: %s" % raw
        if path.is_file():
            key = str(path.resolve())
            if key not in seen:
                seen.add(key)
                found.append(path)
            continue
        for root, dirs, files in os.walk(path, followlinks=False):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in files:
                if Path(name).suffix not in SHELL_EXTENSIONS:
                    continue
                candidate = Path(root) / name
                if any(
                    fnmatch.fnmatch(str(candidate), pattern)
                    for pattern in excludes
                ):
                    continue
                key = str(candidate.resolve())
                if key not in seen:
                    seen.add(key)
                    found.append(candidate)
            if not recursive:
                break
    found.sort(key=str)
    return found, None


def run(paths, recursive=True, excludes=(), use_stdin=False, as_json=False):
    """Run the check. Returns (exit_code, report_dict).

    The report dict holds the checked file count, the problem
    count, and the per-file results. Human-readable lines go to
    stdout (or stderr in JSON mode) by the caller.
    """
    files = []
    stdin_problems = []
    if use_stdin:
        content = sys.stdin.read()
        stdin_problems = check_content(content, "<stdin>")
        files.append(Path("<stdin>"))
    if paths:
        found, error = collect_files(paths, recursive, excludes)
        if error is not None:
            return 2, {"error": error, "files": [], "checked": 0, "problems": 0}
        files.extend(found)
    if not files:
        return 2, {
            "error": "no shell scripts found",
            "files": [],
            "checked": 0,
            "problems": 0,
        }
    results = []
    problems = 0
    for path in files:
        if str(path) == "<stdin>":
            file_problems = stdin_problems
        else:
            file_problems = check_file(path)
        problems += len(file_problems)
        results.append(
            {
                "path": str(path),
                "problems": [p.as_dict() for p in file_problems],
                "error": None,
            }
        )
    return (
        1 if problems else 0,
        {
            "error": None,
            "files": results,
            "checked": len(files),
            "problems": problems,
        },
    )


def report_text(report):
    """The human-readable lines for a report (without the summary)."""
    lines = []
    for entry in report["files"]:
        for problem in entry["problems"]:
            lines.append(
                "FAIL %s:%d: %s"
                % (entry["path"], problem["line"], problem["reason"])
            )
    return lines


def main(argv=None):
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Check shell scripts start with a valid shebang line."
    )
    parser.add_argument(
        "paths", nargs="*", help="files or folders to check"
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="do not walk into subfolders",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="skip files matching this glob pattern (repeatable)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="check one script read from standard input",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON (human lines go to stderr)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="shell-shebang-checker-cli %s" % VERSION,
    )
    args = parser.parse_args(argv)
    if not args.paths and not args.stdin:
        parser.error("give at least one file or folder, or use --stdin")
    exit_code, report = run(
        args.paths,
        recursive=not args.no_recursive,
        excludes=args.exclude,
        use_stdin=args.stdin,
        as_json=args.json,
    )
    if report["error"] is not None:
        print("error: %s" % report["error"], file=sys.stderr)
        return 2
    if args.json:
        for line in report_text(report):
            print(line, file=sys.stderr)
        print(json.dumps(report, indent=2))
        summary_out = sys.stderr
    else:
        for line in report_text(report):
            print(line)
        summary_out = sys.stdout
    checked = report["checked"]
    problems = report["problems"]
    if problems:
        files_with_problems = sum(
            1 for entry in report["files"] if entry["problems"]
        )
        print(
            "Checked %d file(s), %d problem(s) in %d file(s)."
            % (checked, problems, files_with_problems),
            file=summary_out,
        )
    else:
        print(
            "OK — %d file(s) checked, all shell scripts start with "
            "a valid shebang." % checked,
            file=summary_out,
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
