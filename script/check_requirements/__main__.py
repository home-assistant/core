"""CLI entry point for the check_requirements script."""

import argparse
import json
import os
from pathlib import Path
import sys

from .gate import GateDecision, decide_skip
from .models import CheckRunResult
from .runner import run_checks


def _resolve_skip(pr_number: int, head_sha: str | None) -> GateDecision:
    """Decide whether this run can skip re-checking the PR.

    Needs the repo and a token (from the Actions environment) to read prior
    comments; without them it falls open and runs the checks.
    """
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not head_sha or not repo or not token:
        return GateDecision(False, "Gate inputs unavailable; running checks.")
    return decide_skip(pr_number, head_sha, repo, token)


def main(argv: list[str] | None = None) -> int:
    """Run the deterministic check_requirements stage and write its artifact."""
    parser = argparse.ArgumentParser(prog="python -m script.check_requirements")
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument(
        "--head-sha",
        help="PR head commit the checks ran against; embedded in the comment "
        "so a later run can skip when no tracked requirement file changed.",
    )
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

    decision = _resolve_skip(args.pr_number, args.head_sha)
    print(decision.reason, file=sys.stderr)
    if decision.skip:
        result = CheckRunResult(
            pr_number=args.pr_number, head_sha=args.head_sha, skip_aw=True
        )
    else:
        try:
            diff_text = args.diff.read_text(encoding="utf-8")
        except FileNotFoundError:
            parser.error(f"input file {args.diff} not found")
        result = run_checks(
            pr_number=args.pr_number,
            diff_text=diff_text,
            head_sha=args.head_sha,
        )
        print(
            f"check_requirements: {len(result.packages)} package change(s); "
            f"needs_agent={result.needs_agent}",
            file=sys.stderr,
        )

    args.output.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
