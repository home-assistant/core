#!/usr/bin/env python3
"""Add @override decorator to methods listed in a mypy error log."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import re
import subprocess

ERROR_RE = re.compile(r"^(.+?):(\d+): error:.*\[explicit-override\]")


def decorator_stack_top(lines: list[str], def_idx: int) -> int:
    """Return the index of the topmost decorator above the def at def_idx."""
    i = def_idx - 1
    while i >= 0 and lines[i].lstrip().startswith("@"):
        i -= 1
    return i + 1


def main() -> None:
    """Run the script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        default="explicit_override_errors.txt",
        type=Path,
        help="Path to the mypy error log (default: explicit_override_errors.txt)",
    )
    args = parser.parse_args()

    by_file: dict[Path, set[int]] = defaultdict(set)
    for line in args.input.read_text().splitlines():
        if m := ERROR_RE.match(line):
            by_file[Path(m.group(1))].add(int(m.group(2)))

    for path, line_nums in by_file.items():
        lines = path.read_text().splitlines(keepends=True)
        for lineno in sorted(line_nums, reverse=True):
            insert_idx = decorator_stack_top(lines, lineno - 1)
            target = lines[insert_idx]
            indent = target[: len(target) - len(target.lstrip())]
            lines.insert(insert_idx, f"{indent}@override\n")
        first_import = next(
            i for i, ln in enumerate(lines) if ln.startswith(("import ", "from "))
        )
        lines.insert(first_import, "from typing import override\n")
        path.write_text("".join(lines))
        print(f"Updated {path} ({len(line_nums)} methods)")

    if by_file:
        subprocess.run(["ruff", "check", "--fix", *map(str, by_file)], check=False)


if __name__ == "__main__":
    main()
