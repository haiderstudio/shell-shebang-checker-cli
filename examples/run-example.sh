#!/bin/sh
# Run the checker over each example file and over the whole examples
# folder, and show the result. Bad examples fail on purpose, so each
# run is allowed to fail.
cd "$(dirname "$0")/.."
for f in examples/good.sh examples/good-env.sh examples/missing.sh examples/not-first.sh examples/bad-interpreter.sh examples/configs/deploy.sh; do
  echo "== $f =="
  python3 src/shell_shebang_checker.py "$f" || true
  echo
done
echo "== examples/ : the whole folder =="
python3 src/shell_shebang_checker.py examples/ || true
