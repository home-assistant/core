#!/usr/bin/env python3
"""Run mypy on a directory and write `[explicit-override]` errors to a file."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

OUTPUT = Path("explicit_override_errors.txt")

target = sys.argv[1]
result = subprocess.run(
    ["mypy", "--enable-error-code=explicit-override", target],
    capture_output=True,
    text=True,
    check=False,
)
matches = [line for line in result.stdout.splitlines() if "[explicit-override]" in line]
OUTPUT.write_text("\n".join(matches) + ("\n" if matches else ""))
print(f"Wrote {len(matches)} errors to {OUTPUT}")
