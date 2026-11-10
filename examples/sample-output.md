== examples/good.sh ==
OK — 1 file(s) checked, all shell scripts start with a valid shebang.

== examples/good-env.sh ==
OK — 1 file(s) checked, all shell scripts start with a valid shebang.

== examples/missing.sh ==
FAIL examples/missing.sh:1: missing shebang
Checked 1 file(s), 1 problem(s) in 1 file(s).

== examples/not-first.sh ==
FAIL examples/not-first.sh:2: shebang must be on line 1, found on line 2
Checked 1 file(s), 1 problem(s) in 1 file(s).

== examples/bad-interpreter.sh ==
FAIL examples/bad-interpreter.sh:1: interpreter not found: /bin/nosuchshell
Checked 1 file(s), 1 problem(s) in 1 file(s).

== examples/configs/deploy.sh ==
FAIL examples/configs/deploy.sh:1: empty shebang (no interpreter after #!)
Checked 1 file(s), 1 problem(s) in 1 file(s).

== examples/ : the whole folder ==
FAIL examples/bad-interpreter.sh:1: interpreter not found: /bin/nosuchshell
FAIL examples/configs/deploy.sh:1: empty shebang (no interpreter after #!)
FAIL examples/missing.sh:1: missing shebang
FAIL examples/not-first.sh:2: shebang must be on line 1, found on line 2
Checked 7 file(s), 4 problem(s) in 4 file(s).
