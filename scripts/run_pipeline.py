"""End to end pipeline: parse every PDF in data/raw, then load every interim
record into the database. Each stage is idempotent, so the pipeline is too."""

from __future__ import annotations

import os
import subprocess
import sys


def run(cmd: list[str]) -> None:
    env = dict(os.environ, PYTHONPATH=".")
    print(f"\n=== {' '.join(cmd)} ===")
    subprocess.run(cmd, check=True, env=env)


def main() -> None:
    py = sys.executable
    run([py, "scripts/parse_fixtures.py"])
    run([py, "-m", "src.db.load"])


if __name__ == "__main__":
    main()
