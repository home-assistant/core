"""Tests for the PR reviewer collect script."""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from script.pr_reviewer import collect

from . import FakeGh, Reply

NUMBER = 42
HEAD = "c" * 40
REVIEWED = "b" * 40
OLDER = "a" * 40

PULL_REQUEST = f"pulls/{NUMBER}"
REVIEWS = f"pulls/{NUMBER}/reviews"
REVIEW_COMMENTS = f"pulls/{NUMBER}/comments"
THREADS = "graphql"
ISSUE_COMMENTS = f"issues/{NUMBER}/comments"
FILES = f"pulls/{NUMBER}/files"
COMPARE_HEAD = f"compare/dev...{HEAD}"
COMPARE_REVIEWED = f"compare/dev...{REVIEWED}"
COMPARE_SINCE_REVIEW = f"compare/{REVIEWED}...{HEAD}"

BOT = {"login": "github-actions[bot]", "id": 41898282, "type": "Bot"}
CONTRIBUTOR = {"login": "contributor", "id": 1, "type": "User"}
REVIEWER = {"login": "reviewer", "id": 2, "type": "User"}
MARKER = (
    "<!-- gh-aw-agentic-workflow: PR reviewer, workflow_id: pr-reviewer,"
    " run: https://github.com/home-assistant/core/actions/runs/1 -->"
)
OUR_REVIEW_BODY = f"A few suggestions.\n\n{MARKER}"
OTHER_WORKFLOW_REVIEW_BODY = (
    "Quality scale review.\n\n<!-- gh-aw-agentic-workflow: Quality scale reviewer,"
    " workflow_id: quality-scale-reviewer,"
    " run: https://github.com/home-assistant/core/actions/runs/2 -->"
)

SENSOR = "homeassistant/components/demo/sensor.py"
SNAPSHOT = "tests/components/demo/snapshots/test_sensor.ambr"


def file_diff(
    path: str,
    change: str = "+value = 2",
    *,
    index: str = "1111111..2222222",
    hunk: str = "@@ -10,6 +10,7 @@ def setup():",
) -> bytes:
    """Return the diff of one file, as GitHub's compare API does."""
    return (
        f"diff --git a/{path} b/{path}\n"
        f"index {index} 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"{hunk}\n"
        " value = 1\n"
        f"{change}\n"
    ).encode()


PR_DIFF = file_diff(SENSOR)
REVIEWED_PR_DIFF = file_diff(SENSOR, "+value = 3", index="1111111..3333333")
SINCE_REVIEW_DIFF = file_diff(
    SENSOR, "-value = 3\n+value = 2", index="3333333..2222222"
)


def label(name: str) -> dict[str, Any]:
    """Return a label as the GitHub API does."""
    return {"name": name, "color": "ededed", "default": False}


def pull_request(**fields: Any) -> dict[str, Any]:
    """Return an open pull request to dev as the GitHub API does."""
    return {
        "number": NUMBER,
        "title": "Add the température sensor to Démo",
        "body": "Adds a sensor ☀️.",
        "state": "open",
        "draft": False,
        "user": CONTRIBUTOR,
        "head": {"ref": "demo-sensor", "sha": HEAD},
        "base": {"ref": "dev", "sha": "d" * 40},
        "labels": [label("new-feature")],
        **fields,
    }


def review(
    review_id: int, user: dict[str, Any] | None, body: str, **fields: Any
) -> dict[str, Any]:
    """Return a pull request review as the GitHub API does."""
    return {
        "id": review_id,
        "user": user,
        "body": body,
        "state": "COMMENTED",
        "commit_id": REVIEWED,
        "submitted_at": "2026-11-10T10:00:00Z",
        **fields,
    }


def our_review(review_id: int = 1, **fields: Any) -> dict[str, Any]:
    """Return a review this workflow posted."""
    return review(review_id, BOT, OUR_REVIEW_BODY, **fields)


def review_comment(
    comment_id: int,
    user: dict[str, Any],
    review_id: int,
    body: str = "Use a constant.",
    **fields: Any,
) -> dict[str, Any]:
    """Return a pull request review comment as the GitHub API does."""
    return {
        "id": comment_id,
        "pull_request_review_id": review_id,
        "user": user,
        "body": body,
        "path": SENSOR,
        "line": 12,
        "start_line": None,
        "side": "RIGHT",
        "original_line": 12,
        "commit_id": HEAD,
        "original_commit_id": REVIEWED,
        "created_at": "2026-11-10T10:00:00Z",
        "html_url": (
            f"https://github.com/home-assistant/core/pull/{NUMBER}"
            f"#discussion_r{comment_id}"
        ),
        **fields,
    }


def thread(comment_id: int, **fields: Any) -> dict[str, Any]:
    """Return a review thread as the GitHub GraphQL API does."""
    return {
        "isResolved": False,
        "isOutdated": False,
        "resolvedBy": None,
        "comments": {"nodes": [{"databaseId": comment_id}]},
        **fields,
    }


def threads_page(*threads: dict[str, Any]) -> dict[str, Any]:
    """Return a page of review threads as the GitHub GraphQL API does."""
    return {
        "data": {
            "repository": {"pullRequest": {"reviewThreads": {"nodes": list(threads)}}}
        }
    }


def issue_comment(comment_id: int, user: dict[str, Any], body: str) -> dict[str, Any]:
    """Return a pull request comment as the GitHub API does."""
    return {
        "id": comment_id,
        "user": user,
        "body": body,
        "created_at": "2026-11-11T09:00:00Z",
        "html_url": (
            f"https://github.com/home-assistant/core/pull/{NUMBER}"
            f"#issuecomment-{comment_id}"
        ),
    }


def changed_file(
    filename: str, additions: int = 1, deletions: int = 0
) -> dict[str, Any]:
    """Return a changed file of a pull request as the GitHub API does."""
    return {
        "filename": filename,
        "status": "modified",
        "additions": additions,
        "deletions": deletions,
        "changes": additions + deletions,
    }


def changed_files(
    count: int,
    filename: str = "homeassistant/components/demo/f{}.py",
    additions: int = 1,
) -> list[dict[str, Any]]:
    """Return changed files of a pull request, numbering the filename."""
    return [changed_file(filename.format(i), additions) for i in range(count)]


@dataclass
class Collector:
    """Run collect.py on the pull request and read what it produced."""

    monkeypatch: pytest.MonkeyPatch
    capsys: pytest.CaptureFixture[str]
    out_dir: Path
    github_output: Path

    def run(
        self, head_sha: str = HEAD, options: tuple[str, ...] = ("--set-outputs",)
    ) -> None:
        """Run the script."""
        self.monkeypatch.setattr(
            sys,
            "argv",
            ["collect.py", *options, str(NUMBER), str(self.out_dir), head_sha],
        )
        collect.main()

    def json(self, name: str) -> Any:
        """Return the data of a JSON file in the out dir."""
        return json.loads((self.out_dir / name).read_text(encoding="utf-8"))

    def assert_skipped(self, reason: str) -> None:
        """Assert the script decided not to review the pull request."""
        assert self.json("task.json") == {
            "review": False,
            "reviewed_head": None,
            "reason": reason,
        }
        assert (
            self.capsys.readouterr().out
            == f"::notice title=PR review skipped::{reason}\n"
        )
        assert self.github_output.read_text(encoding="utf-8") == "skip=true\n"

    def assert_reviewed(self, reviewed_head: str | None = None) -> None:
        """Assert the script decided to review the pull request head."""
        assert self.json("task.json") == {
            "review": True,
            "reviewed_head": reviewed_head,
        }
        assert self.capsys.readouterr().out == ""
        assert self.github_output.read_text(encoding="utf-8") == f"head_sha={HEAD}\n"


@pytest.fixture(autouse=True)
def pull_request_routes(gh: FakeGh) -> None:
    """Serve an open pull request without reviews or comments."""
    gh.json(PULL_REQUEST, pull_request())
    gh.json(REVIEWS, [[]])
    gh.json(REVIEW_COMMENTS, [[]])
    gh.json(THREADS, [threads_page()])
    gh.json(ISSUE_COMMENTS, [[]])
    gh.json(FILES, [[changed_file(SENSOR)]])
    gh.reply(COMPARE_HEAD, Reply(PR_DIFF))


@pytest.fixture
def earlier_review(gh: FakeGh) -> None:
    """Serve our review of the pull request at REVIEWED, and the diffs since."""
    gh.json(REVIEWS, [[our_review()]])
    gh.reply(COMPARE_REVIEWED, Reply(REVIEWED_PR_DIFF))
    gh.reply(COMPARE_SINCE_REVIEW, Reply(SINCE_REVIEW_DIFF))


@pytest.fixture
def collector(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    github_output: Path,
) -> Collector:
    """Return a runner of collect.py, writing to an out dir that does not exist yet."""
    return Collector(
        monkeypatch, capsys, tmp_path / "runner" / "pr-reviewer", github_output
    )


def test_not_a_pull_request(gh: FakeGh, collector: Collector) -> None:
    """Test a number that is not a pull request is skipped."""
    gh.error(PULL_REQUEST, "gh: Not Found (HTTP 404)\n")

    collector.run()

    collector.assert_skipped(f"#{NUMBER} is not a pull request")


def test_pull_request_fetch_fails(gh: FakeGh, collector: Collector) -> None:
    """Test a failed pull request fetch fails the script with gh's error."""
    gh.error(PULL_REQUEST, "gh: Server Error (HTTP 500)\n")

    with pytest.raises(SystemExit) as exc_info:
        collector.run()

    assert exc_info.value.code == "gh: Server Error (HTTP 500)\n"
    assert not (collector.out_dir / "task.json").exists()
    assert not collector.github_output.exists()


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        pytest.param(
            {"state": "closed"},
            f"#{NUMBER} isn't an open, non-draft pull request to dev",
            id="closed",
        ),
        pytest.param(
            {"draft": True},
            f"#{NUMBER} isn't an open, non-draft pull request to dev",
            id="draft",
        ),
        pytest.param(
            {"base": {"ref": "master", "sha": "d" * 40}},
            f"#{NUMBER} isn't an open, non-draft pull request to dev",
            id="not-to-dev",
        ),
        pytest.param(
            {"labels": [label("new-feature"), label("pr-reviewer-muted")]},
            f"#{NUMBER} is muted with the pr-reviewer-muted label",
            id="muted",
        ),
    ],
)
def test_pull_request_skipped(
    gh: FakeGh, collector: Collector, fields: dict[str, Any], reason: str
) -> None:
    """Test closed, draft, muted and pull requests to other branches are skipped."""
    gh.json(PULL_REQUEST, pull_request(**fields))

    collector.run()

    collector.assert_skipped(reason)


def test_head_moved(collector: Collector) -> None:
    """Test a pull request that moved on from the commit to review is skipped."""
    collector.run(OLDER)

    collector.assert_skipped(f"#{NUMBER} moved on to {HEAD}, which its own run reviews")


def test_head_sha_empty(collector: Collector) -> None:
    """Test an empty head sha, from a dispatched run, reviews the pull request head."""
    collector.run("")

    collector.assert_reviewed()


def test_first_review(
    gh: FakeGh, collector: Collector, snapshot: SnapshotAssertion
) -> None:
    """Test the files written for the first review of a pull request."""
    gh.json(
        REVIEWS,
        [
            [
                review(
                    1,
                    REVIEWER,
                    "Ça a l'air bien 👍",
                    commit_id=OLDER,
                    submitted_at="2026-11-09T08:00:00Z",
                )
            ]
        ],
    )
    gh.json(
        REVIEW_COMMENTS,
        [
            [
                review_comment(10, REVIEWER, 1, "Utiliser « °C » ici ?"),
                review_comment(11, CONTRIBUTOR, 2, "Fait ✅", in_reply_to_id=10),
            ]
        ],
    )
    gh.json(
        THREADS,
        [
            threads_page(
                thread(10, isResolved=True, resolvedBy={"login": "contributor"})
            )
        ],
    )
    gh.json(ISSUE_COMMENTS, [[issue_comment(20, CONTRIBUTOR, "Merci — 谢谢")]])

    collector.run()

    collector.assert_reviewed()
    assert {
        name: (collector.out_dir / name).read_text(encoding="utf-8")
        for name in (
            "pr.json",
            "reviews.json",
            "review-comments.json",
            "threads.json",
            "issue-comments.json",
        )
    } == snapshot
    assert (collector.out_dir / "pr.diff").read_bytes() == PR_DIFF
    assert not (collector.out_dir / "since-review.diff").exists()


def test_pr_json(gh: FakeGh, collector: Collector) -> None:
    """Test pr.json keeps a missing body and has only the label names."""
    gh.json(
        PULL_REQUEST,
        pull_request(
            body=None, labels=[label("new-feature"), label("integration: demo")]
        ),
    )

    collector.run()

    pr = collector.json("pr.json")
    assert pr["body"] is None
    assert pr["labels"] == ["new-feature", "integration: demo"]


@pytest.mark.parametrize(
    ("user", "body", "ours"),
    [
        pytest.param(BOT, OUR_REVIEW_BODY, True, id="bot-with-marker"),
        pytest.param(BOT, OTHER_WORKFLOW_REVIEW_BODY, False, id="bot-without-marker"),
        pytest.param(REVIEWER, OUR_REVIEW_BODY, False, id="other-user-with-marker"),
        pytest.param(None, OUR_REVIEW_BODY, False, id="ghost"),
    ],
)
@pytest.mark.usefixtures("earlier_review")
def test_reviews_ours(
    gh: FakeGh,
    collector: Collector,
    user: dict[str, Any] | None,
    body: str,
    ours: bool,
) -> None:
    """Test only the bot's reviews with the workflow's marker are ours."""
    gh.json(REVIEWS, [[review(1, user, body)]])

    collector.run()

    assert [review["ours"] for review in collector.json("reviews.json")] == [ours]


def test_review_comments_thread(gh: FakeGh, collector: Collector) -> None:
    """Test review comments name their thread by its first comment."""
    gh.json(
        REVIEW_COMMENTS,
        [
            [
                review_comment(10, REVIEWER, 1),
                review_comment(11, CONTRIBUTOR, 2, in_reply_to_id=10),
            ]
        ],
    )

    collector.run()

    assert [
        comment["thread"] for comment in collector.json("review-comments.json")
    ] == [10, 10]


@pytest.mark.parametrize(
    ("review_body", "comments", "ours"),
    [
        pytest.param(
            OUR_REVIEW_BODY, [review_comment(10, BOT, 1)], [True], id="our-review"
        ),
        pytest.param(
            OTHER_WORKFLOW_REVIEW_BODY,
            [review_comment(10, BOT, 1)],
            [False],
            id="bot-review-without-marker",
        ),
        pytest.param(
            OUR_REVIEW_BODY,
            [
                review_comment(10, BOT, 1),
                review_comment(11, CONTRIBUTOR, 2, in_reply_to_id=10),
            ],
            [True, False],
            id="human-reply-in-our-thread",
        ),
    ],
)
@pytest.mark.usefixtures("earlier_review")
def test_review_comments_ours(
    gh: FakeGh,
    collector: Collector,
    review_body: str,
    comments: list[dict[str, Any]],
    ours: list[bool],
) -> None:
    """Test only the bot's comments of our reviews are ours."""
    gh.json(REVIEWS, [[review(1, BOT, review_body)]])
    gh.json(REVIEW_COMMENTS, [comments])

    collector.run()

    assert [
        comment["ours"] for comment in collector.json("review-comments.json")
    ] == ours


def test_threads(gh: FakeGh, collector: Collector) -> None:
    """Test the review threads."""
    gh.json(
        THREADS,
        [
            threads_page(
                thread(10, isResolved=True, resolvedBy={"login": "contributor"}),
                thread(20, isOutdated=True),
            )
        ],
    )

    collector.run()

    assert collector.json("threads.json") == [
        {
            "thread": 10,
            "resolved": True,
            "outdated": False,
            "resolved_by": "contributor",
        },
        {"thread": 20, "resolved": False, "outdated": True, "resolved_by": None},
    ]


def test_pagination(gh: FakeGh, collector: Collector) -> None:
    """Test every page of reviews, comments and threads is written."""
    gh.json(REVIEWS, [[review(1, REVIEWER, "First")], [review(2, REVIEWER, "Second")]])
    gh.json(
        REVIEW_COMMENTS,
        [[review_comment(10, REVIEWER, 1)], [review_comment(11, REVIEWER, 2)]],
    )
    gh.json(THREADS, [threads_page(thread(10)), threads_page(thread(11))])
    gh.json(
        ISSUE_COMMENTS,
        [
            [issue_comment(20, CONTRIBUTOR, "First")],
            [issue_comment(21, CONTRIBUTOR, "Second")],
        ],
    )

    collector.run()

    assert [review["id"] for review in collector.json("reviews.json")] == [1, 2]
    assert [comment["id"] for comment in collector.json("review-comments.json")] == [
        10,
        11,
    ]
    assert [thread["thread"] for thread in collector.json("threads.json")] == [10, 11]
    assert [comment["id"] for comment in collector.json("issue-comments.json")] == [
        20,
        21,
    ]


@pytest.mark.parametrize(
    "pages",
    [
        pytest.param([[changed_file(SENSOR, 2500, 2500)]], id="5000-lines"),
        pytest.param([changed_files(100)], id="100-files"),
        pytest.param(
            [
                [
                    changed_file(SENSOR),
                    *changed_files(
                        101, "tests/components/demo/snapshots/test_{}.ambr", 50
                    ),
                ]
            ],
            id="snapshots-not-counted",
        ),
    ],
)
def test_size_within_limit(
    gh: FakeGh, collector: Collector, pages: list[list[dict[str, Any]]]
) -> None:
    """Test a pull request within the size limit, not counting test snapshots, is reviewed."""
    gh.json(FILES, pages)

    collector.run()

    collector.assert_reviewed()


@pytest.mark.parametrize(
    ("pages", "reason"),
    [
        pytest.param(
            [[changed_file(SENSOR, 2500, 2501)]],
            f"#{NUMBER} changes 5001 lines in 1 files, above the limit of 5000 lines"
            " and 100 files",
            id="5001-lines",
        ),
        pytest.param(
            [
                changed_files(100),
                [changed_file("homeassistant/components/demo/f100.py")],
            ],
            f"#{NUMBER} changes 101 lines in 101 files, above the limit of 5000 lines"
            " and 100 files",
            id="101-files",
        ),
    ],
)
def test_size_over_limit(
    gh: FakeGh,
    collector: Collector,
    pages: list[list[dict[str, Any]]],
    reason: str,
) -> None:
    """Test a pull request over the size limit is skipped."""
    gh.json(FILES, pages)

    collector.run()

    collector.assert_skipped(reason)
    assert not (collector.out_dir / "pr.diff").exists()


@pytest.mark.parametrize(
    "reviews",
    [
        pytest.param(
            [
                our_review(1, commit_id=OLDER, submitted_at="2026-11-01T10:00:00Z"),
                our_review(2, commit_id=REVIEWED, submitted_at="2026-11-10T10:00:00Z"),
            ],
            id="latest-of-ours",
        ),
        pytest.param(
            [
                our_review(1),
                review(
                    2,
                    REVIEWER,
                    "Looks good.",
                    commit_id=HEAD,
                    submitted_at="2026-11-12T10:00:00Z",
                ),
                review(
                    3,
                    BOT,
                    OTHER_WORKFLOW_REVIEW_BODY,
                    commit_id=HEAD,
                    submitted_at="2026-11-13T10:00:00Z",
                ),
            ],
            id="newer-reviews-not-ours",
        ),
    ],
)
@pytest.mark.usefixtures("earlier_review")
def test_reviewed_head(
    gh: FakeGh, collector: Collector, reviews: list[dict[str, Any]]
) -> None:
    """Test the reviewed head is the commit of our latest review."""
    gh.json(REVIEWS, [reviews])

    collector.run()

    collector.assert_reviewed(REVIEWED)


def test_already_reviewed(gh: FakeGh, collector: Collector) -> None:
    """Test a pull request we reviewed at its head is skipped."""
    gh.json(REVIEWS, [[our_review(commit_id=HEAD)]])

    collector.run()

    collector.assert_skipped(f"#{NUMBER} was already reviewed at {HEAD}")


def test_pr_diff_without_snapshots(gh: FakeGh, collector: Collector) -> None:
    """Test pr.diff drops the test snapshots and keeps the other files as is."""
    init = file_diff("homeassistant/components/demo/__init__.py")
    sensor = file_diff(
        SENSOR, '+    _attr_name = "Température"\n\\ No newline at end of file'
    )
    gh.reply(
        COMPARE_HEAD,
        Reply(
            init
            + file_diff(SNAPSHOT)
            + sensor
            + file_diff("tests/components/demo/snapshots/test_init.ambr")
        ),
    )

    collector.run()

    assert (collector.out_dir / "pr.diff").read_bytes() == init + sensor


def test_only_snapshots(gh: FakeGh, collector: Collector) -> None:
    """Test a pull request changing only test snapshots is skipped."""
    gh.json(FILES, [[changed_file(SNAPSHOT)]])
    gh.reply(COMPARE_HEAD, Reply(file_diff(SNAPSHOT)))

    collector.run()

    collector.assert_skipped(f"No diff for #{NUMBER} outside test snapshots")
    assert (collector.out_dir / "pr.diff").read_bytes() == b""


@pytest.mark.usefixtures("earlier_review")
def test_re_review(collector: Collector) -> None:
    """Test a changed pull request is reviewed with the diff since our review."""
    collector.run()

    collector.assert_reviewed(REVIEWED)
    assert (collector.out_dir / "since-review.diff").read_bytes() == SINCE_REVIEW_DIFF


@pytest.mark.usefixtures("earlier_review")
def test_re_review_only_dev_merged(gh: FakeGh, collector: Collector) -> None:
    """Test a pull request that only merged dev since our review is skipped."""
    gh.reply(
        COMPARE_REVIEWED,
        Reply(
            file_diff(
                SENSOR, index="3333333..4444444", hunk="@@ -8,6 +8,7 @@ def setup():"
            )
        ),
    )

    collector.run()

    collector.assert_skipped(f"The diff of #{NUMBER} is unchanged since {REVIEWED}")
    assert (collector.out_dir / "pr.diff").read_bytes() == PR_DIFF
    assert not (collector.out_dir / "since-review.diff").exists()


@pytest.mark.usefixtures("earlier_review")
def test_re_review_function_context_changed(gh: FakeGh, collector: Collector) -> None:
    """Test a changed function context of a hunk is a changed diff."""
    gh.reply(
        COMPARE_REVIEWED,
        Reply(file_diff(SENSOR, hunk="@@ -10,6 +10,7 @@ async def async_setup():")),
    )

    collector.run()

    collector.assert_reviewed(REVIEWED)


@pytest.mark.usefixtures("earlier_review")
def test_since_review_diff_files(gh: FakeGh, collector: Collector) -> None:
    """Test the diff since our review keeps only the files of the pull request."""
    light = "homeassistant/components/demo/light.py"
    switch = "homeassistant/components/demo/switch.py"
    gh.reply(
        COMPARE_HEAD,
        Reply(file_diff(light) + file_diff(SENSOR) + file_diff(SNAPSHOT)),
    )
    gh.reply(
        COMPARE_REVIEWED,
        Reply(file_diff(switch) + file_diff(SENSOR, "+value = 3")),
    )
    in_pr_diff = file_diff(light)
    in_reviewed_diff = file_diff(switch, "-value = 2")
    in_both = file_diff(SENSOR, "-value = 3\n+value = 2")
    gh.reply(
        COMPARE_SINCE_REVIEW,
        Reply(
            in_pr_diff
            + in_reviewed_diff
            + in_both
            + file_diff("homeassistant/core.py")
            + file_diff(SNAPSHOT, "+  'state': '21.5',")
        ),
    )

    collector.run()

    assert (
        collector.out_dir / "since-review.diff"
    ).read_bytes() == in_pr_diff + in_reviewed_diff + in_both


@pytest.mark.usefixtures("earlier_review")
def test_re_review_comparisons_fail(gh: FakeGh, collector: Collector) -> None:
    """Test a pull request is reviewed without the diff since our review if GitHub refuses it."""
    gh.error(COMPARE_REVIEWED, "gh: Not Found (HTTP 404)\n")
    gh.error(COMPARE_SINCE_REVIEW, "gh: Not Found (HTTP 404)\n")

    collector.run()

    collector.assert_reviewed(REVIEWED)
    assert (collector.out_dir / "pr.diff").read_bytes() == PR_DIFF
    assert not (collector.out_dir / "since-review.diff").exists()


def test_pr_diff_fails(gh: FakeGh, collector: Collector) -> None:
    """Test a failed pull request diff fails the script."""
    gh.error(COMPARE_HEAD, "gh: Server Error (HTTP 502)\n")

    with pytest.raises(subprocess.CalledProcessError):
        collector.run()

    assert not (collector.out_dir / "task.json").exists()


def test_without_set_outputs(collector: Collector) -> None:
    """Test GITHUB_OUTPUT is left untouched without --set-outputs."""
    collector.run(options=())

    assert not collector.github_output.exists()
