#!/usr/bin/env python3
"""Tests for shell-shebang-checker-cli.

Run: python3 tests/test_shell_shebang_checker.py
Standard library only (unittest).
"""

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "shell_shebang_checker.py"
TEST_FILE = Path(__file__).resolve()

sys.path.insert(0, str(REPO_ROOT / "src"))
import shell_shebang_checker as ssc


def run_cli(*args, input_text=None, cwd=None):
    """Run the real CLI as a subprocess. Returns (exit, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(SRC), *args],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=cwd or str(REPO_ROOT),
    )
    return result.returncode, result.stdout, result.stderr


def problems_of(content):
    """The (line, reason) pairs check_content finds in one script."""
    return [(p.lineno, p.reason) for p in ssc.check_content(content, "x.sh")]


class TestShebangParsing(unittest.TestCase):
    def test_plain_sh_passes(self):
        self.assertEqual(problems_of("#!/bin/sh\necho hi\n"), [])

    def test_bash_with_args_passes(self):
        self.assertEqual(problems_of("#!/bin/bash -e\necho hi\n"), [])

    def test_space_after_hashbang_passes(self):
        self.assertEqual(problems_of("#! /bin/sh\necho hi\n"), [])

    def test_trailing_space_passes(self):
        self.assertEqual(problems_of("#!/bin/sh  \necho hi\n"), [])

    def test_crlf_passes(self):
        self.assertEqual(problems_of("#!/bin/sh\r\necho hi\r\n"), [])

    def test_env_bash_passes(self):
        self.assertEqual(problems_of("#!/usr/bin/env bash\necho hi\n"), [])

    def test_env_with_dash_s_passes(self):
        self.assertEqual(problems_of("#!/usr/bin/env -S bash\necho hi\n"), [])

    def test_env_with_args_passes(self):
        self.assertEqual(problems_of("#!/usr/bin/env -S python3 -u\n"), [])

    def test_env_with_ignore_environment_flag_passes(self):
        self.assertEqual(problems_of("#!/usr/bin/env -i bash\n"), [])

    def test_empty_file_is_missing(self):
        self.assertEqual(
            problems_of(""), [(1, "missing shebang")]
        )

    def test_blank_only_file_is_missing(self):
        self.assertEqual(
            problems_of("\n"), [(1, "missing shebang")]
        )

    def test_comment_first_line_is_missing(self):
        self.assertEqual(
            problems_of("# a comment\necho hi\n"),
            [(1, "missing shebang")],
        )

    def test_empty_shebang(self):
        self.assertEqual(
            problems_of("#!\n\necho hi\n"),
            [(1, "empty shebang (no interpreter after #!)")],
        )

    def test_shebang_spaces_only_is_empty(self):
        self.assertEqual(
            problems_of("#!   \necho hi\n"),
            [(1, "empty shebang (no interpreter after #!)")],
        )

    def test_shebang_on_line_two(self):
        self.assertEqual(
            problems_of("\n#!/bin/sh\necho hi\n"),
            [(2, "shebang must be on line 1, found on line 2")],
        )

    def test_shebang_after_code(self):
        content = "echo a\necho b\necho c\necho d\n#!/bin/sh\n"
        self.assertEqual(
            problems_of(content),
            [(5, "shebang must be on line 1, found on line 5")],
        )

    def test_leading_space_before_shebang_is_missing(self):
        self.assertEqual(
            problems_of(" #!/bin/sh\necho hi\n"),
            [(1, "missing shebang")],
        )

    def test_nonexistent_interpreter(self):
        self.assertEqual(
            problems_of("#!/bin/nosuchshell\necho hi\n"),
            [(1, "interpreter not found: /bin/nosuchshell")],
        )

    def test_relative_interpreter(self):
        self.assertEqual(
            problems_of("#!python3\necho hi\n"),
            [(1, "interpreter is not an absolute path: python3")],
        )

    def test_env_with_no_program(self):
        self.assertEqual(
            problems_of("#!/usr/bin/env\necho hi\n"),
            [(1, "no program after /usr/bin/env")],
        )

    def test_env_with_missing_program(self):
        self.assertEqual(
            problems_of("#!/usr/bin/env nosuchprog123\necho hi\n"),
            [(1, "interpreter not found: nosuchprog123")],
        )

    def test_env_dash_s_with_missing_program(self):
        self.assertEqual(
            problems_of("#!/usr/bin/env -S nosuchprog123\necho hi\n"),
            [(1, "interpreter not found: nosuchprog123")],
        )

    def test_bom_before_shebang_is_missing(self):
        self.assertEqual(
            problems_of("\ufeff#!/bin/sh\necho hi\n"),
            [(1, "missing shebang")],
        )

    def test_non_executable_interpreter(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "myshell"
            fake.write_text("#!/bin/sh\n")
            fake.chmod(0o644)
            self.assertEqual(
                problems_of("#!%s\necho hi\n" % fake),
                [(1, "interpreter not executable: %s" % fake)],
            )

    def test_valid_shebang_later_lines_ignored(self):
        # Once line 1 is a good shebang, the rest is not our job.
        self.assertEqual(
            problems_of("#!/bin/sh\n#!/bin/nosuchshell\necho hi\n"), []
        )


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relpath, content):
        path = self.root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_clean_file_exit_zero(self):
        self.write("ok.sh", "#!/bin/sh\necho hi\n")
        code, out, err = run_cli("ok.sh", cwd=self.root)
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out)
        self.assertEqual(err, "")

    def test_bad_file_exit_one(self):
        self.write("bad.sh", "echo hi\n")
        code, out, err = run_cli("bad.sh", cwd=self.root)
        self.assertEqual(code, 1)
        self.assertIn("FAIL bad.sh:1: missing shebang", out)
        self.assertIn("Checked 1 file(s), 1 problem(s) in 1 file(s).", out)

    def test_folder_walk_sh_only(self):
        self.write("a.sh", "#!/bin/sh\n")
        self.write("b.sh", "echo hi\n")
        self.write("c.txt", "echo hi\n")
        self.write("sub/d.sh", "#!/bin/sh\n")
        code, out, err = run_cli(".", cwd=self.root)
        self.assertEqual(code, 1)
        self.assertIn("Checked 3 file(s), 1 problem(s) in 1 file(s).", out)
        self.assertIn("FAIL b.sh:1: missing shebang", out)
        self.assertNotIn("c.txt", out)

    def test_git_folder_skipped(self):
        self.write(".git/hook.sh", "echo hi\n")
        self.write("ok.sh", "#!/bin/sh\n")
        code, out, err = run_cli(".", cwd=self.root)
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out)

    def test_no_recursive(self):
        self.write("a.sh", "#!/bin/sh\n")
        self.write("sub/b.sh", "echo hi\n")
        code, out, err = run_cli("--no-recursive", ".", cwd=self.root)
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out)

    def test_exclude_pattern(self):
        self.write("a.sh", "#!/bin/sh\n")
        self.write("b.sh", "echo hi\n")
        code, out, err = run_cli("--exclude", "*b.sh", ".", cwd=self.root)
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out)

    def test_direct_file_any_name(self):
        self.write("deploy", "#!/bin/sh\necho hi\n")
        self.write("nodeploy", "echo hi\n")
        code, out, err = run_cli("deploy", "nodeploy", cwd=self.root)
        self.assertEqual(code, 1)
        self.assertIn("FAIL nodeploy:1: missing shebang", out)

    def test_same_file_twice_checked_once(self):
        self.write("a.sh", "echo hi\n")
        code, out, err = run_cli("a.sh", "a.sh", cwd=self.root)
        self.assertEqual(code, 1)
        self.assertIn("Checked 1 file(s), 1 problem(s)", out)

    def test_missing_path_exit_two(self):
        code, out, err = run_cli("nope.sh", cwd=self.root)
        self.assertEqual(code, 2)
        self.assertIn("error: no such file or directory", err)

    def test_no_args_exit_two(self):
        code, out, err = run_cli(cwd=self.root)
        self.assertEqual(code, 2)

    def test_bad_flag_exit_two(self):
        code, out, err = run_cli("--frobnicate", cwd=self.root)
        self.assertEqual(code, 2)

    def test_empty_folder_exit_two(self):
        code, out, err = run_cli(".", cwd=self.root)
        self.assertEqual(code, 2)
        self.assertIn("error: no shell scripts found", err)

    def test_version(self):
        code, out, err = run_cli("--version", cwd=self.root)
        self.assertEqual(code, 0)
        self.assertIn("shell-shebang-checker-cli", out)

    def test_stdin_clean(self):
        code, out, err = run_cli("--stdin", input_text="#!/bin/sh\necho hi\n")
        self.assertEqual(code, 0)
        self.assertIn("OK — 1 file(s) checked", out)

    def test_stdin_bad(self):
        code, out, err = run_cli("--stdin", input_text="echo hi\n")
        self.assertEqual(code, 1)
        self.assertIn("FAIL <stdin>:1: missing shebang", out)

    def test_json_output_parses(self):
        self.write("bad.sh", "echo hi\n")
        code, out, err = run_cli("--json", "bad.sh", cwd=self.root)
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["checked"], 1)
        self.assertEqual(data["problems"], 1)
        self.assertEqual(
            data["files"][0]["problems"],
            [{"line": 1, "reason": "missing shebang"}],
        )
        self.assertIn("FAIL bad.sh:1: missing shebang", err)

    def test_json_clean_parses(self):
        self.write("ok.sh", "#!/bin/sh\n")
        code, out, err = run_cli("--json", "ok.sh", cwd=self.root)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["problems"], 0)

    def test_non_utf8_file_reported(self):
        path = self.root / "bad.sh"
        path.write_bytes(b"#!/bin/sh\n\xff\xfe\n")
        code, out, err = run_cli("bad.sh", cwd=self.root)
        self.assertEqual(code, 1)
        self.assertIn("cannot read file (not valid UTF-8)", out)

    def test_input_files_unchanged(self):
        target = self.write("a.sh", "#!/bin/sh\necho hi\n")
        before = target.read_bytes()
        run_cli("a.sh", cwd=self.root)
        self.assertEqual(target.read_bytes(), before)


class TestExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        saved = (REPO_ROOT / "examples" / "sample-output.md").read_text()
        self.assertEqual(result.stdout, saved)

    def test_readme_text_blocks_match_live_runs(self):
        readme = (REPO_ROOT / "README.md").read_text()
        blocks = re.findall(r"```text\n(.*?)```", readme, re.DOTALL)
        self.assertTrue(blocks, "no ```text blocks found in README")
        live = []
        for args in (
            ["examples/good.sh"],
            ["examples/missing.sh"],
            ["examples/not-first.sh"],
            ["examples/bad-interpreter.sh"],
            ["examples/good-env.sh"],
            ["examples/"],
        ):
            code, out, err = run_cli(*args)
            live.append(out)
        code, out, err = run_cli(
            "--stdin", input_text=(REPO_ROOT / "examples" / "missing.sh").read_text()
        )
        live.append(out)
        joined = "\n".join(live)
        for block in blocks:
            self.assertIn(
                block.strip(), joined, "README text block not in live output"
            )

    def test_readme_json_block_matches_live_run(self):
        readme = (REPO_ROOT / "README.md").read_text()
        match = re.search(r"```json\n(.*?)```", readme, re.DOTALL)
        self.assertIsNotNone(match, "no ```json block found in README")
        expected = json.loads(match.group(1))
        code, out, err = run_cli("--json", "examples/missing.sh")
        self.assertEqual(json.loads(out), expected)

    def test_examples_folder_run_counts(self):
        code, out, err = run_cli("examples/")
        self.assertEqual(code, 1)
        self.assertIn("Checked 7 file(s), 4 problem(s) in 4 file(s).", out)


class TestHygiene(unittest.TestCase):
    BANNED = ["TODO", "FIXME", "coming soon", "lorem"]

    def repo_files(self):
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file():
                continue
            parts = path.relative_to(REPO_ROOT).parts
            if ".git" in parts or "__pycache__" in parts:
                continue
            if parts[0] == "tests":
                continue
            yield path

    def test_no_banned_words(self):
        for path in self.repo_files():
            text = path.read_text(errors="ignore")
            for word in self.BANNED:
                self.assertNotIn(
                    word, text, "%s contains banned word %r" % (path, word)
                )

    def test_no_absolute_paths(self):
        for path in self.repo_files():
            text = path.read_text(errors="ignore")
            self.assertNotIn("/home/", text, "%s contains /home/" % path)
            self.assertNotIn("/Users/", text, "%s contains /Users/" % path)

    def test_stdlib_only_imports(self):
        stdlib = set(sys.stdlib_module_names)
        for path in (REPO_ROOT / "src").glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(
                            alias.name.split(".")[0],
                            stdlib,
                            "%s imports non-stdlib %s" % (path, alias.name),
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self.assertIn(
                            node.module.split(".")[0],
                            stdlib,
                            "%s imports non-stdlib %s" % (path, node.module),
                        )

    def test_no_yaml_import(self):
        for path in list((REPO_ROOT / "src").glob("*.py")) + list(
            (REPO_ROOT / ".github").rglob("*")
        ):
            if path.is_file():
                self.assertNotIn(
                    "yaml", path.read_text(errors="ignore").lower()
                )

    def test_gitignore_env_first(self):
        lines = (REPO_ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_the_test_file(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("tests/test_shell_shebang_checker.py", ci)


if __name__ == "__main__":
    unittest.main()
