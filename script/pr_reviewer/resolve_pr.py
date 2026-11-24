#!/usr/bin/env python3
"""Resolve the pull request a PR reviewer workflow run is for.

Usage: script/pr_reviewer/resolve_pr.py

Writes `pr_number` to GITHUB_OUTPUT, or `skip=true` when there is none.

Needs EVENT_NAME and GITHUB_OUTPUT, plus INPUT_PR_NUMBER on a workflow_dispatch
run, or RUN_ID and RUN_TITLE on a workflow_run one.
"""

import os
from pathlib import Path
import re


def main() -> None:
    """Write the pull request number, or to skip, to GITHUB_OUTPUT."""
    if os.environ["EVENT_NAME"] == "workflow_dispatch":
        output = f"pr_number={os.environ['INPUT_PR_NUMBER']}"
    # The run name can come from a fork's copy of the trigger: never print it.
    elif match := re.fullmatch(r"#([1-9][0-9]{0,9})", os.environ["RUN_TITLE"]):
        output = f"pr_number={match[1]}"
    else:
        print(
            "::notice title=PR review skipped::No pull request number in the name"
            f" of trigger run {os.environ['RUN_ID']}"
        )
        output = "skip=true"
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as file:
        file.write(f"{output}\n")


if __name__ == "__main__":
    main()
