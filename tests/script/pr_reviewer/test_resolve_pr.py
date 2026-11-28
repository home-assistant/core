"""Tests for the PR reviewer resolve_pr script."""

from pathlib import Path

import pytest

from script.pr_reviewer import resolve_pr

RUN_ID = "19876543210"


@pytest.fixture
def workflow_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the environment of a run started by a trigger run."""
    monkeypatch.setenv("EVENT_NAME", "workflow_run")
    monkeypatch.setenv("RUN_ID", RUN_ID)
    monkeypatch.delenv("INPUT_PR_NUMBER", raising=False)


def test_workflow_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    github_output: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test a dispatched run is for the pull request of its input."""
    monkeypatch.setenv("EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("INPUT_PR_NUMBER", "42")
    monkeypatch.delenv("RUN_ID", raising=False)
    monkeypatch.delenv("RUN_TITLE", raising=False)

    resolve_pr.main()

    assert github_output.read_text(encoding="utf-8") == "pr_number=42\n"
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("title", "output"),
    [
        pytest.param("#1", "pr_number=1\n", id="1"),
        pytest.param("#42", "pr_number=42\n", id="42"),
        pytest.param("#1234567890", "pr_number=1234567890\n", id="10-digits"),
        pytest.param("", "skip=true\n", id="empty"),
        pytest.param("#0", "skip=true\n", id="zero"),
        pytest.param("#12345678901", "skip=true\n", id="11-digits"),
        pytest.param("#42\nskip=true", "skip=true\n", id="extra-output"),
        pytest.param("Update the README", "skip=true\n", id="free-text"),
    ],
)
@pytest.mark.usefixtures("workflow_run")
def test_workflow_run(
    monkeypatch: pytest.MonkeyPatch, github_output: Path, title: str, output: str
) -> None:
    """Test a triggered run is for the pull request in the trigger run's name, if any."""
    monkeypatch.setenv("RUN_TITLE", title)

    resolve_pr.main()

    assert github_output.read_text(encoding="utf-8") == output


@pytest.mark.usefixtures("workflow_run", "github_output")
def test_skip_notice(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test the skip notice names the trigger run, never its name."""
    monkeypatch.setenv("RUN_TITLE", "#42 ::error::Injected")

    resolve_pr.main()

    assert capsys.readouterr().out == (
        "::notice title=PR review skipped::No pull request number in the name"
        f" of trigger run {RUN_ID}\n"
    )
