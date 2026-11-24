#!/usr/bin/env python3
"""Wait for earlier PR reviewer runs for a pull request to finish posting.

Usage: script/pr_reviewer/wait_for_runs.py <pr-number>

Needs GH_TOKEN, GITHUB_REPOSITORY and GITHUB_RUN_ID.

Runs for the same pull request take turns in the agent job, but one whose agent
job has finished may still be posting. Waiting for it lets this run see what it
posted.
"""

import argparse
import json
import os
import subprocess
import time
from typing import Any

WORKFLOW = "pr-reviewer.lock.yml"
ACTIVE_STATUSES = ("queued", "in_progress", "waiting", "pending")
AGENT_DONE = {"success", "failure", "timed_out"}
# 12 minutes at most, so the agent step's own timeout still fits in the job's.
ATTEMPTS = 36
INTERVAL = 20


def gh_api(*args: str) -> Any:
    """Return the parsed output of `gh api`, which prints its errors to stderr."""
    return json.loads(
        subprocess.run(["gh", "api", *args], stdout=subprocess.PIPE, check=True).stdout
    )


def earlier_run_posting(repo: str, run_id: int, title: str) -> bool:
    """Return whether another run with the title may be posting."""
    for status in ACTIVE_STATUSES:
        pages = gh_api(
            "--paginate",
            "--slurp",
            f"repos/{repo}/actions/workflows/{WORKFLOW}/runs"
            f"?status={status}&per_page=100",
        )
        for run in (run for page in pages for run in page["workflow_runs"]):
            if run["id"] == run_id or run["display_title"] != title:
                continue
            jobs = gh_api(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")
            if any(
                job["name"] == "agent" and job["conclusion"] in AGENT_DONE
                for job in jobs["jobs"]
            ):
                return True
    return False


def main() -> None:
    """Wait until no earlier run for the pull request is posting."""
    parser = argparse.ArgumentParser(
        description="Wait for earlier PR reviewer runs to finish posting."
    )
    parser.add_argument("pr_number", type=int)
    args = parser.parse_args()

    repo = os.environ["GITHUB_REPOSITORY"]
    run_id = int(os.environ["GITHUB_RUN_ID"])
    for _ in range(ATTEMPTS):
        try:
            posting = earlier_run_posting(
                repo, run_id, f"PR reviewer: #{args.pr_number}"
            )
        except subprocess.CalledProcessError:
            # An API error counts as posting.
            posting = True
        if not posting:
            return
        time.sleep(INTERVAL)
    print(
        f"::warning::Earlier runs for #{args.pr_number} are still posting after"
        f" {ATTEMPTS * INTERVAL // 60} minutes"
    )


if __name__ == "__main__":
    main()
