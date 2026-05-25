"""CLI entry point for the check_requirements script."""

import argparse
import json
from pathlib import Path
import sys

from .runner import run_checks


def main(argv: list[str] | None = None) -> int:
    """Run the deterministic check_requirements stage and write its artifact."""
    parser = argparse.ArgumentParser(prog="python -m script.check_requirements")
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument(
        "--diff",
        type=Path,
        required=True,
        help="Path to a file containing the unified PR diff.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path where the results.json artifact will be written.",
    )
    args = parser.parse_args(argv)

    try:
        diff_text = args.diff.read_text(encoding="utf-8")
    except FileNotFoundError:
        parser.error(f"input file {args.diff} not found")
    result = run_checks(
        pr_number=args.pr_number,
        diff_text=diff_text,
    )
    args.output.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"check_requirements: {len(result.packages)} package change(s); "
        f"needs_agent={result.needs_agent}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
