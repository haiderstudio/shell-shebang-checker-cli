# shell-shebang-checker-cli

Check shell scripts start with a valid shebang, fail CI on a missing shebang.

[![CI](https://github.com/haiderstudio/shell-shebang-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/shell-shebang-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`shell_shebang_checker` reads shell scripts and checks that
each one starts with a valid shebang line — `#!` followed by an
interpreter that exists on this machine and can be executed —
and reports every file that is missing one, has one that is
not on line 1, or names an interpreter that does not exist.
It exits 1 when any problem is found, so it can fail a CI run.
A file with a good shebang exits 0.

- A script with no shebang runs under the wrong shell (or not
  at all) when executed directly. This tool catches that
  before the script ships, instead of after someone runs it
  and gets a confusing error.
- A valid shebang is `#!` at the very start of line 1,
  followed by an absolute interpreter path (`#!/bin/sh`,
  `#!/bin/bash -e`) or the env form (`#!/usr/bin/env bash`,
  `#!/usr/bin/env -S python3 -u`). A space after `#!`
  (`#! /bin/sh`) is fine.
- The interpreter is checked against this machine: a direct
  path must exist and be executable, and an `env` program
  must be on PATH. `#!/bin/nosuchshell` and
  `#!/usr/bin/env nosuchprog` both fail.
- A shebang found on line 2 or later fails — the kernel only
  reads line 1, so a shebang further down never takes effect.
  An empty shebang (`#!` with nothing after it) fails, and
  so does a relative interpreter (`#!python3`).
- A file given directly on the command line is always checked,
  whatever its name. A folder is walked for shell scripts
  (`.sh`), recursively by default (`--no-recursive` stops at
  the top level). `.git` folders are never walked, and
  directory links are never followed.
- `--json` prints the result as JSON (the human-readable lines
  go to standard error), and `--stdin` checks one script read
  from standard input.

## Who it is for

Anyone who ships shell scripts — open-source maintainers,
teams that keep deploy or setup scripts in a repo, and anyone
who has ever run a script and watched it fail because the
wrong shell picked it up.

## What it does NOT do

- It does not check whether a script is correct — a script
  with a good shebang can still have bugs in it. This tool
  checks the first line only.
- It does not check executable permissions. A script without
  the executable bit still passes if its shebang is good;
  that is a different check.
- It does not check scripts written for another machine: the
  interpreter must exist on the machine running the check.
  A script that names an interpreter installed somewhere else
  will fail here, by design.
- It does not check any other file type in a folder walk, and
  it never rewrites a file. It is report-only, and it never
  touches the network.

## How this differs

- justiceandmercy/shebang-check (0 stars) is the closest
  rival: a Python tool that audits shebang lines in a codebase
  for missing interpreters, misplaced shebangs, and executable
  files without one. It ships no tests and no CI workflow.
  This tool is a tested stdlib-only CLI with a CI workflow
  that fails the build, exact line numbers for every problem,
  folder walking, and `--json`/`--stdin` output.
- xuhdev/flake8-executable (20 stars) is a Flake8 plugin that
  checks executable permissions and shebangs — it needs
  Flake8 installed and runs as part of a lint pass, not as a
  standalone gate. This tool needs nothing but Python.

## Install

```sh
git clone https://github.com/haiderstudio/shell-shebang-checker-cli.git
cd shell-shebang-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one file:

```sh
python3 src/shell_shebang_checker.py examples/good.sh
```

A clean file passes:

```sh
$ python3 src/shell_shebang_checker.py examples/good.sh
```

```text
OK — 1 file(s) checked, all shell scripts start with a valid shebang.
```

A file with no shebang fails:

```sh
$ python3 src/shell_shebang_checker.py examples/missing.sh
```

```text
FAIL examples/missing.sh:1: missing shebang
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

A shebang on the wrong line fails:

```sh
$ python3 src/shell_shebang_checker.py examples/not-first.sh
```

```text
FAIL examples/not-first.sh:2: shebang must be on line 1, found on line 2
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

A shebang naming an interpreter that does not exist fails:

```sh
$ python3 src/shell_shebang_checker.py examples/bad-interpreter.sh
```

```text
FAIL examples/bad-interpreter.sh:1: interpreter not found: /bin/nosuchshell
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Check a whole folder (shell scripts only):

```sh
python3 src/shell_shebang_checker.py scripts/
```

Check one script from standard input:

```sh
$ python3 src/shell_shebang_checker.py --stdin < examples/missing.sh
```

```text
FAIL <stdin>:1: missing shebang
Checked 1 file(s), 1 problem(s) in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/shell_shebang_checker.py --json examples/missing.sh
```

```json
{
  "error": null,
  "files": [
    {
      "path": "examples/missing.sh",
      "problems": [
        {
          "line": 1,
          "reason": "missing shebang"
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "problems": 1
}
```

Exit codes: 0 when no file checked has a problem, 1 when
any problem is found or a file cannot be read, 2 for a usage
error (a missing path, a bad flag, or no shell scripts found).

## Examples

The env form passes when the program is on PATH:

```sh
$ python3 src/shell_shebang_checker.py examples/good-env.sh
```

```text
OK — 1 file(s) checked, all shell scripts start with a valid shebang.
```

A whole folder, including a file in a subfolder:

```sh
$ python3 src/shell_shebang_checker.py examples/
```

```text
FAIL examples/bad-interpreter.sh:1: interpreter not found: /bin/nosuchshell
FAIL examples/configs/deploy.sh:1: empty shebang (no interpreter after #!)
FAIL examples/missing.sh:1: missing shebang
FAIL examples/not-first.sh:2: shebang must be on line 1, found on line 2
Checked 7 file(s), 4 problem(s) in 4 file(s).
```

The folder run counts `examples/run-example.sh` too, so it
checks 7 files. Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_shell_shebang_checker.py
```

The tests cover shebang parsing (direct paths with and
without arguments, the env form with and without `-S`, a
space after `#!`, trailing spaces, CRLF endings, a BOM
before the shebang), every problem type with exact line
numbers (missing shebang, empty shebang, shebang not on
line 1, interpreter not found, interpreter not executable,
interpreter not an absolute path, no program after env),
the CLI (exit 0/1/2, folder walking, shell scripts only,
`.git` skipped, `--no-recursive`, `--exclude`, a direct file
checked even without a `.sh` name, same file twice checked
once, `--stdin`, `--json` output that parses as JSON,
`--version`, bad flags, missing paths, empty folders, a
non-UTF-8 file reported, input files left unchanged), the
bundled examples (sample output compared byte-for-byte
against a fresh run, and the README-quoted outputs checked
against live runs), and hygiene checks (no placeholder
text, no absolute paths, stdlib imports only, `.env` first
in `.gitignore`, CI file runs the test file).

## Contributing

Small, focused improvements are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

This is original work, written for this repo. The idea of
checking shebangs in CI is a common one; the closest
existing tool is named in "How this differs" above.
No code was copied from it.
