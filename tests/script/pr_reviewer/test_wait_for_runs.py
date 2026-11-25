"""Tests for the PR reviewer wait_for_runs script."""

import sys
import time
from typing import Any
from unittest.mock import Mock, call

import pytest

from script.pr_reviewer import wait_for_runs

from . import FakeGh, error_reply, json_reply

RUNS = "actions/workflows/pr-reviewer.lock.yml/runs?status={}"
IN_PROGRESS_RUNS = RUNS.format("in_progress")
OTHER_RUN = 2002
OTHER_RUN_JOBS = f"actions/runs/{OTHER_RUN}/jobs"


def workflow_run(run_id: int, pr_number: int = 42) -> dict[str, Any]:
    """Return a run of the workflow as the GitHub API does."""
    return {
        "id": run_id,
        "name": "PR reviewer",
        "display_title": f"PR reviewer: #{pr_number}",
        "status": "in_progress",
    }


def runs_page(*runs: dict[str, Any]) -> dict[str, Any]:
    """Return a page of workflow runs as the GitHub API does."""
    return {"total_count": len(runs), "workflow_runs": list(runs)}


def job(name: str, conclusion: str | None, status: str = "completed") -> dict[str, Any]:
    """Return a job of a run as the GitHub API does."""
    return {"name": name, "status": status, "conclusion": conclusion}


def jobs_page(*jobs: dict[str, Any]) -> dict[str, Any]:
    """Return the jobs of a run as the GitHub API does."""
    return {"total_count": len(jobs), "jobs": list(jobs)}


NO_RUNS = [runs_page()]
OTHER_RUN_ACTIVE = [runs_page(workflow_run(OTHER_RUN))]


@pytest.fixture(autouse=True)
def no_active_runs(gh: FakeGh, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the script for #42 in run 2001, with no other active runs."""
    monkeypatch.setenv("GITHUB_RUN_ID", "2001")
    monkeypatch.setattr(sys, "argv", ["wait_for_runs.py", "42"])
    for status in ("queued", "in_progress", "waiting", "pending"):
        gh.json(RUNS.format(status), NO_RUNS)


@pytest.fixture
def sleep(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock the sleeps between checks."""
    mock = Mock()
    monkeypatch.setattr(time, "sleep", mock)
    return mock


@pytest.mark.parametrize("conclusion", ["success", "failure", "timed_out"])
def test_agent_done(
    gh: FakeGh, sleep: Mock, capsys: pytest.CaptureFixture[str], conclusion: str
) -> None:
    """Test the script waits for a run whose agent job is done."""
    gh.json(IN_PROGRESS_RUNS, OTHER_RUN_ACTIVE, NO_RUNS)
    gh.json(
        OTHER_RUN_JOBS, jobs_page(job("prepare", "success"), job("agent", conclusion))
    )

    wait_for_runs.main()

    sleep.assert_called_once_with(20)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("runs", "jobs"),
    [
        pytest.param(NO_RUNS, [], id="no-active-runs"),
        pytest.param(
            [runs_page(workflow_run(OTHER_RUN, 7))],
            [job("agent", "success")],
            id="other-pull-request",
        ),
        pytest.param(
            OTHER_RUN_ACTIVE,
            [job("prepare", "success"), job("agent", None, "in_progress")],
            id="agent-running",
        ),
        pytest.param(
            OTHER_RUN_ACTIVE,
            [job("prepare", "success"), job("agent", "cancelled")],
            id="agent-cancelled",
        ),
        pytest.param(
            OTHER_RUN_ACTIVE,
            [job("prepare", "success"), job("agent", "skipped")],
            id="agent-skipped",
        ),
        pytest.param(
            OTHER_RUN_ACTIVE,
            [job("pre_activation", "success"), job("prepare", "success")],
            id="other-jobs-done",
        ),
        pytest.param(OTHER_RUN_ACTIVE, [], id="no-jobs"),
    ],
)
def test_nothing_posting(
    gh: FakeGh,
    sleep: Mock,
    capsys: pytest.CaptureFixture[str],
    runs: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
) -> None:
    """Test the script does not wait without a run for the pull request that posts."""
    gh.json(IN_PROGRESS_RUNS, runs)
    gh.json(OTHER_RUN_JOBS, jobs_page(*jobs))

    wait_for_runs.main()

    sleep.assert_not_called()
    assert capsys.readouterr().out == ""


def test_posting_then_done(
    gh: FakeGh, sleep: Mock, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test the script checks again every 20 seconds until no run is posting."""
    gh.json(IN_PROGRESS_RUNS, OTHER_RUN_ACTIVE, OTHER_RUN_ACTIVE, NO_RUNS)
    gh.json(OTHER_RUN_JOBS, jobs_page(job("agent", "success")))

    wait_for_runs.main()

    assert sleep.call_args_list == [call(20), call(20)]
    assert capsys.readouterr().out == ""


def test_still_posting(
    gh: FakeGh, sleep: Mock, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test the script warns after its last check, without waiting again."""
    gh.json(IN_PROGRESS_RUNS, OTHER_RUN_ACTIVE)
    gh.json(OTHER_RUN_JOBS, jobs_page(job("agent", "success")))

    wait_for_runs.main()

    assert sleep.call_args_list == [call(20)] * 35
    assert (
        capsys.readouterr().out
        == "::warning::Earlier runs for #42 are still posting after 11 minutes\n"
    )


def test_api_error(gh: FakeGh, sleep: Mock, capsys: pytest.CaptureFixture[str]) -> None:
    """Test the script waits and checks again when the GitHub API fails."""
    gh.reply(
        RUNS.format("queued"),
        error_reply("gh: Server Error (HTTP 502)\n"),
        json_reply(NO_RUNS),
    )

    wait_for_runs.main()

    sleep.assert_called_once_with(20)
    assert capsys.readouterr().out == ""
