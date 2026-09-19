"""CLI entry point for the quality_scale_review script."""

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys

from . import artifact, github_api, integrations, rules
from .models import PullRequest, Results

MAX_CHANGED_LINES = 4000
MAX_CHANGED_FILES = 50


@dataclass(slots=True, frozen=True)
class SkipDecision:
    """Whether to skip the review, and why.

    `reason` continues the sentence "this pull request ..." in the comment the
    agentic stage posts on a pull request that is too long to review.
    """

    skip: bool
    too_long: bool
    reason: str


def decide_skip(
    pr: PullRequest,
    domains: list[str],
    *,
    max_changed_lines: int = MAX_CHANGED_LINES,
    max_changed_files: int = MAX_CHANGED_FILES,
) -> SkipDecision:
    """Decide whether this pull request is reviewed.

    It is skipped when it is too large to review reliably, or when it touches
    no integration that declares a quality scale.
    """
    if pr.changed_lines > max_changed_lines or pr.changed_files > max_changed_files:
        return SkipDecision(
            skip=True,
            too_long=True,
            reason=(
                f"changes {pr.changed_lines} lines in {pr.changed_files} files, "
                f"above the limit of {max_changed_lines} lines "
                f"and {max_changed_files} files"
            ),
        )
    if not domains:
        return SkipDecision(
            skip=True,
            too_long=False,
            reason="touches no integration with a quality_scale.yaml",
        )
    return SkipDecision(skip=False, too_long=False, reason="")


def main(argv: list[str] | None = None) -> int:
    """Collect the pull request data and quality scale rules for the reviewer."""
    parser = argparse.ArgumentParser(prog="python -m script.quality_scale_review")
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="`owner/name` of the repository the pull request belongs to.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory the artifact is written to.",
    )
    parser.add_argument("--max-changed-lines", type=int, default=MAX_CHANGED_LINES)
    parser.add_argument("--max-changed-files", type=int, default=MAX_CHANGED_FILES)
    args = parser.parse_args(argv)
    if not args.repo:
        parser.error("--repo is required when GITHUB_REPOSITORY is unset")
    if not (token := os.environ.get("GITHUB_TOKEN")):
        parser.error("GITHUB_TOKEN is unset")

    pr = github_api.fetch_pull_request(args.repo, args.pr_number, token)
    domains = integrations.with_quality_scale(
        integrations.touched_domains(pr.filenames), pr.file_statuses
    )
    decision = decide_skip(
        pr,
        domains,
        max_changed_lines=args.max_changed_lines,
        max_changed_files=args.max_changed_files,
    )
    artifact.write_pull_request(
        args.output,
        Results(
            pr_number=pr.number,
            head_sha=pr.head_sha,
            skip=decision.skip,
            too_long=decision.too_long,
            skip_reason=decision.reason,
            changed_lines=pr.changed_lines,
            changed_files=pr.changed_files,
            domains=domains,
        ),
        pr,
    )
    print(
        f"PR #{pr.number}: skip={decision.skip} {decision.reason}; "
        f"domains: {', '.join(domains)}",
        file=sys.stderr,
    )
    if decision.skip:
        return 0

    diff = github_api.fetch_diff(args.repo, args.pr_number, token)
    artifact.write_diff(args.output, diff)
    docs = rules.fetch_docs(token)
    index = rules.build_index(docs)
    artifact.write_rules(args.output, index, docs.rules)
    print(
        f"{diff.count('\n')} diff lines, {len(index.splitlines()) - 1} rules in index, "
        f"{len(docs.rules)} rule docs",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
