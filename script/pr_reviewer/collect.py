#!/usr/bin/env python3
"""Collect what the PR reviewer workflow needs for one pull request.

Decides whether to review it, in task.json.

Usage: script/pr_reviewer/collect.py [--write-github-output] <pr-number> <out-dir> [<head-sha>]

Needs GH_TOKEN and GITHUB_REPOSITORY. <head-sha> pins the commit to review;
it defaults to the pull request's head. --write-github-output also writes `head_sha`
to GITHUB_OUTPUT, or `skip=true` when there is nothing to review.

The workflow keeps no state of its own and reads it back from the pull request:
its reviews carry gh-aw's hidden marker, and the commit of its last complete
review is the reviewed head.
"""

import argparse
from contextlib import suppress
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

BOT = "github-actions[bot]"
# Part of the hidden marker gh-aw adds to this workflow's review bodies.
MARKER = "workflow_id: pr-reviewer,"
# Closes the body of a finished review: gh-aw also posts reviews cut short.
COMPLETE_MARKER = "completed_review: true"
MAX_CHANGED_LINES = 5000
MAX_CHANGED_FILES = 100
MAX_SNAPSHOT_DIFF_LINES = 4000
FILE_DIFF_START = re.compile(rb"^(?=diff --git )", re.MULTILINE)
INDEX_LINE = re.compile(rb"^index .*\n?", re.MULTILINE)
HUNK_RANGES = re.compile(rb"^@@ -[0-9,]+ \+[0-9,]+ @@", re.MULTILINE)
THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $endCursor: String) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) {
    reviewThreads(first: 100, after: $endCursor) {
      nodes {
        isResolved isOutdated resolvedBy { login }
        comments(first: 1) { nodes { databaseId } }
      }
      pageInfo { hasNextPage endCursor }
    }
  } }
}
"""


class Skip(Exception):
    """The pull request is not to be reviewed."""


def gh_api(*args: str) -> bytes:
    """Return the output of `gh api`, which prints its errors to stderr."""
    return subprocess.run(
        ["gh", "api", *args], stdout=subprocess.PIPE, check=True
    ).stdout


def gh_list(path: str) -> list[dict[str, Any]]:
    """Return every item of a paginated REST list."""
    pages = json.loads(gh_api("--paginate", "--slurp", path))
    return [item for page in pages for item in page]


def pick(item: dict[str, Any], *keys: str) -> dict[str, Any]:
    """Return the given fields of an item, as null when missing."""
    return {key: item.get(key) for key in keys}


def author(item: dict[str, Any]) -> dict[str, Any]:
    """Return the login and type of an item's author, who may be missing."""
    user = item["user"] or {}
    return {"user": user.get("login"), "user_type": user.get("type")}


def write_json(path: Path, data: Any) -> None:
    """Write data to a JSON file."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def diff_path(file_diff: bytes) -> bytes:
    """Return the path a file's diff changes, from its `diff --git` line."""
    return file_diff.partition(b"\n")[0].rpartition(b" b/")[2]


def diff_paths(diff: bytes) -> set[bytes]:
    """Return the paths a diff changes."""
    return {diff_path(file_diff) for file_diff in FILE_DIFF_START.split(diff)}


def pr_diff(repo: str, base: str, head: str, paths: set[bytes] | None = None) -> bytes:
    """Return the diff from base to head, as GitHub shows it.

    With paths, only the diffs of those files are kept.
    """
    diff = gh_api(
        "-H",
        "Accept: application/vnd.github.diff",
        f"repos/{repo}/compare/{base}...{head}",
    )
    return b"".join(
        file_diff
        for file_diff in FILE_DIFF_START.split(diff)
        if paths is None or diff_path(file_diff) in paths
    )


def split_snapshots(diff: bytes) -> tuple[bytes, bytes]:
    """Split a diff into that of the code and that of the test snapshots."""
    code: list[bytes] = []
    snapshots: list[bytes] = []
    for file_diff in FILE_DIFF_START.split(diff):
        (snapshots if diff_path(file_diff).endswith(b".ambr") else code).append(
            file_diff
        )
    return b"".join(code), b"".join(snapshots)


def review_diff(diff: bytes, with_snapshots: bool) -> bytes:
    """Return a diff with its test snapshots last, or without them."""
    code_diff, snapshot_diff = split_snapshots(diff)
    return code_diff + snapshot_diff if with_snapshots else code_diff


def diff_id(diff: bytes) -> str:
    """Return a hash of a diff that ignores line numbers and blob IDs.

    The same changes on a newer base then match.
    """
    return hashlib.sha256(HUNK_RANGES.sub(b"@@", INDEX_LINE.sub(b"", diff))).hexdigest()


def collect(
    repo: str, number: int, out: Path, head_sha: str | None
) -> tuple[str, str | None]:
    """Write what the review of a pull request needs.

    Returns the head to review and the reviewed head. Raises Skip when there is
    nothing to review.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{number}"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode:
        if "HTTP 404" not in result.stderr:
            sys.exit(result.stderr)
        raise Skip(f"#{number} is not a pull request")
    pr = json.loads(result.stdout)
    if pr["state"] != "open" or pr["draft"] or pr["base"]["ref"] != "dev":
        raise Skip(f"#{number} isn't an open, non-draft pull request to dev")
    labels = [label["name"] for label in pr["labels"]]
    if "pr-reviewer-muted" in labels:
        raise Skip(f"#{number} is muted with the pr-reviewer-muted label")
    current_head = pr["head"]["sha"]
    head_sha = head_sha or current_head
    # Reviewing the older commit after the newer one would make it the reviewed head.
    if head_sha != current_head:
        raise Skip(f"#{number} moved on to {current_head}, which its own run reviews")
    base = pr["base"]["ref"]

    write_json(
        out / "pr.json",
        {
            **pick(pr, "number", "title", "body"),
            "author": author(pr)["user"],
            "head_sha": head_sha,
            "base": base,
            "labels": labels,
        },
    )

    reviews = [
        {
            **pick(review, "id", "state", "commit_id", "submitted_at", "body"),
            **author(review),
        }
        for review in gh_list(f"repos/{repo}/pulls/{number}/reviews?per_page=100")
    ]
    for review in reviews:
        review["ours"] = review["user"] == BOT and MARKER in (review["body"] or "")
        review["complete"] = review["ours"] and COMPLETE_MARKER in review["body"]
    write_json(out / "reviews.json", reviews)
    our_reviews = {review["id"] for review in reviews if review["ours"]}

    comments = [
        {
            **pick(
                comment,
                "id",
                "path",
                "line",
                "start_line",
                "side",
                "original_line",
                "commit_id",
                "original_commit_id",
                "created_at",
                "body",
            ),
            **author(comment),
            # Replies always point at the first comment of their thread, which names the thread.
            "thread": comment.get("in_reply_to_id") or comment["id"],
            "review_id": comment["pull_request_review_id"],
            "url": comment["html_url"],
        }
        for comment in gh_list(f"repos/{repo}/pulls/{number}/comments?per_page=100")
    ]
    for comment in comments:
        comment["ours"] = comment["user"] == BOT and comment["review_id"] in our_reviews
    write_json(out / "review-comments.json", comments)

    owner, name = repo.split("/")
    pages = json.loads(
        gh_api(
            "graphql",
            "--paginate",
            "--slurp",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={number}",
            "-f",
            f"query={THREADS_QUERY}",
        )
    )
    write_json(
        out / "threads.json",
        [
            {
                "thread": next(
                    (comment["databaseId"] for comment in thread["comments"]["nodes"]),
                    None,
                ),
                "resolved": thread["isResolved"],
                "outdated": thread["isOutdated"],
                "resolved_by": (thread["resolvedBy"] or {}).get("login"),
            }
            for page in pages
            for thread in page["data"]["repository"]["pullRequest"]["reviewThreads"][
                "nodes"
            ]
        ],
    )

    write_json(
        out / "issue-comments.json",
        [
            {
                **pick(comment, "id", "created_at", "body"),
                **author(comment),
                "url": comment["html_url"],
            }
            for comment in gh_list(
                f"repos/{repo}/issues/{number}/comments?per_page=100"
            )
        ],
    )

    files = [
        file
        for file in gh_list(f"repos/{repo}/pulls/{number}/files?per_page=100")
        if not file["filename"].endswith(".ambr")
    ]
    changed_lines = sum(file["additions"] + file["deletions"] for file in files)
    if changed_lines > MAX_CHANGED_LINES or len(files) > MAX_CHANGED_FILES:
        raise Skip(
            f"#{number} changes {changed_lines} lines in {len(files)} files, above"
            f" the limit of {MAX_CHANGED_LINES} lines and {MAX_CHANGED_FILES} files"
        )
    complete = sorted(
        (review for review in reviews if review["complete"]),
        key=lambda review: review["submitted_at"] or "",
    )
    reviewed_head = complete[-1]["commit_id"] if complete else None
    if reviewed_head == head_sha:
        raise Skip(f"#{number} was already reviewed at {head_sha}")

    diff = pr_diff(repo, base, head_sha)
    _, snapshot_diff = split_snapshots(diff)
    # The review leaves out test snapshots too long to check.
    with_snapshots = snapshot_diff.count(b"\n") <= MAX_SNAPSHOT_DIFF_LINES
    to_review = review_diff(diff, with_snapshots)
    if not to_review:
        raise Skip(f"No diff for #{number} to review")
    (out / "pr.diff").write_bytes(to_review)
    if reviewed_head:
        # Merges from dev bring in changes to any file: keep the PR's files, then and now.
        paths = diff_paths(diff)
        # A diff GitHub refuses counts as changed.
        with suppress(subprocess.CalledProcessError):
            reviewed_diff = pr_diff(repo, base, reviewed_head)
            # Only dev merged in since the last review: the diff to review is unchanged.
            if diff_id(review_diff(reviewed_diff, with_snapshots)) == diff_id(
                to_review
            ):
                raise Skip(f"The diff of #{number} is unchanged since {reviewed_head}")
            paths |= diff_paths(reviewed_diff)
        with suppress(subprocess.CalledProcessError):
            (out / "since-review.diff").write_bytes(
                review_diff(
                    pr_diff(repo, reviewed_head, head_sha, paths), with_snapshots
                )
            )
    return head_sha, reviewed_head


def main() -> None:
    """Collect a pull request and write whether to review it to task.json."""
    parser = argparse.ArgumentParser(
        description="Collect what the PR reviewer workflow needs for one pull request."
    )
    parser.add_argument(
        "--write-github-output",
        action="store_true",
        help="write head_sha, or skip=true, to GITHUB_OUTPUT",
    )
    parser.add_argument("pr_number", type=int)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument(
        "head_sha", nargs="?", help="commit to review, the pull request's head if empty"
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        head_sha, reviewed_head = collect(
            os.environ["GITHUB_REPOSITORY"], args.pr_number, args.out_dir, args.head_sha
        )
    except Skip as skip:
        print(f"::notice title=PR review skipped::{skip}")
        task = {"review": False, "reviewed_head": None, "reason": str(skip)}
        output = "skip=true"
    else:
        task = {"review": True, "reviewed_head": reviewed_head}
        output = f"head_sha={head_sha}"
    write_json(args.out_dir / "task.json", task)
    if args.write_github_output:
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as file:
            file.write(f"{output}\n")


if __name__ == "__main__":
    main()
