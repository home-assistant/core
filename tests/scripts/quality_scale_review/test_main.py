"""Tests for script.quality_scale_review.__main__."""

import json
from pathlib import Path

import pytest

from script.quality_scale_review import __main__, github_api, integrations, rules
from script.quality_scale_review.__main__ import (
    MAX_CHANGED_FILES,
    MAX_CHANGED_LINES,
    decide_skip,
)
from script.quality_scale_review.models import PullRequest, RuleDoc

_REPO = "home-assistant/core"

_DIFF = "diff --git a/x b/x\n+added\n"
_DOCS = rules.QualityScaleDocs(
    tiers={"bronze": ["config-flow"], "silver": [], "gold": [], "platinum": []},
    rules=[RuleDoc("config-flow.md", '---\ntitle: "Config flow"\n---\n')],
)


def _pull_request(
    additions: int = 30, deletions: int = 12, files: int = 3
) -> PullRequest:
    """Return a pull request touching the peblar integration."""
    return PullRequest(
        number=42,
        title="Add peblar sensors",
        body="Body text",
        head_sha="abc123",
        base_ref="dev",
        additions=additions,
        deletions=deletions,
        changed_files=files,
        file_statuses={"homeassistant/components/peblar/sensor.py": "modified"},
    )


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide the Actions environment the script reads."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", _REPO)


@pytest.fixture
def stub_github(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer every GitHub call with a peblar pull request and one rule."""
    monkeypatch.setattr(github_api, "fetch_pull_request", lambda *args: _pull_request())
    monkeypatch.setattr(integrations, "with_quality_scale", lambda domains, *a: domains)
    monkeypatch.setattr(github_api, "fetch_diff", lambda *args: _DIFF)
    monkeypatch.setattr(rules, "fetch_docs", lambda token: _DOCS)


def test_reviewed_when_within_limits_and_a_domain_is_touched() -> None:
    """A small pull request touching a quality scale integration is reviewed."""
    decision = decide_skip(_pull_request(), ["peblar"])
    assert (decision.skip, decision.too_long, decision.reason) == (False, False, "")


def test_skipped_when_no_domain_has_a_quality_scale() -> None:
    """Without a domain there is nothing to review against."""
    decision = decide_skip(_pull_request(), [])
    assert (decision.skip, decision.too_long) == (True, False)
    assert decision.reason == "touches no integration with a quality_scale.yaml"


@pytest.mark.parametrize(
    ("additions", "deletions", "files"),
    [
        pytest.param(MAX_CHANGED_LINES + 1, 0, 1, id="too-many-lines"),
        pytest.param(0, MAX_CHANGED_LINES + 1, 1, id="too-many-deleted-lines"),
        pytest.param(1, 1, MAX_CHANGED_FILES + 1, id="too-many-files"),
    ],
)
def test_skipped_when_too_long(additions: int, deletions: int, files: int) -> None:
    """A pull request above either limit is too long to review."""
    decision = decide_skip(_pull_request(additions, deletions, files), ["peblar"])
    assert (decision.skip, decision.too_long) == (True, True)
    assert decision.reason.startswith(
        f"changes {additions + deletions} lines in {files} files, above the limit of "
    )


def test_reason_reads_as_a_sentence_about_the_pull_request() -> None:
    """The reason is rendered after "this pull request" in the posted comment."""
    decision = decide_skip(_pull_request(5000, 0, 10), ["peblar"])
    assert decision.reason == (
        "changes 5000 lines in 10 files, above the limit of 4000 lines and 50 files"
    )


def test_limits_can_be_overridden() -> None:
    """The caller can tighten the limits."""
    decision = decide_skip(
        _pull_request(10, 5, 3), ["peblar"], max_changed_lines=10, max_changed_files=300
    )
    assert decision.too_long is True


def test_the_size_limit_wins_over_the_missing_domain() -> None:
    """A too long pull request is reported as too long, not as out of scope."""
    decision = decide_skip(_pull_request(MAX_CHANGED_LINES + 1, 0, 1), [])
    assert decision.too_long is True


@pytest.mark.usefixtures("stub_github")
def test_writes_the_full_artifact_for_a_reviewed_pull_request(tmp_path: Path) -> None:
    """A reviewed pull request ships the diff and the rules alongside its data."""
    output = tmp_path / "deterministic"

    assert __main__.main(["--pr-number", "42", "--output", str(output)]) == 0

    results = json.loads((output / "results.json").read_text())
    assert results["skip"] is False
    assert results["too_long"] is False
    assert results["skip_reason"] == ""
    assert results["pr_number"] == 42
    assert results["head_sha"] == "abc123"
    assert results["changed_lines"] == 42
    assert results["domains"] == ["peblar"]
    assert json.loads((output / "pr-meta.json").read_text())["headRefOid"] == "abc123"
    assert (output / "domains.txt").read_text() == "peblar\n"
    assert (output / "pr-diff.patch").read_text() == _DIFF
    assert (output / "rules-index.txt").read_text().splitlines()[1] == (
        "bronze | config-flow | Config flow"
    )
    assert (output / "rules" / "config-flow.md").exists()


def test_skips_a_pull_request_without_a_quality_scale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without a domain the diff and the rules are not collected."""
    monkeypatch.setattr(github_api, "fetch_pull_request", lambda *args: _pull_request())
    monkeypatch.setattr(integrations, "with_quality_scale", lambda *args: [])

    assert __main__.main(["--pr-number", "42", "--output", str(tmp_path)]) == 0

    results = json.loads((tmp_path / "results.json").read_text())
    assert results["skip"] is True
    assert results["too_long"] is False
    assert results["skip_reason"] == "touches no integration with a quality_scale.yaml"
    assert results["domains"] == []
    assert not (tmp_path / "pr-diff.patch").exists()
    assert not (tmp_path / "rules-index.txt").exists()


def test_skips_a_pull_request_that_is_too_long(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A pull request above the size limit is flagged for the too long comment."""
    monkeypatch.setattr(
        github_api, "fetch_pull_request", lambda *args: _pull_request(additions=5000)
    )
    monkeypatch.setattr(integrations, "with_quality_scale", lambda domains, *a: domains)

    assert __main__.main(["--pr-number", "42", "--output", str(tmp_path)]) == 0

    results = json.loads((tmp_path / "results.json").read_text())
    assert results["skip"] is True
    assert results["too_long"] is True
    assert results["skip_reason"].startswith("changes 5012 lines in 3 files")
    assert not (tmp_path / "pr-diff.patch").exists()


@pytest.mark.usefixtures("stub_github")
def test_the_size_limits_can_be_overridden_from_the_command_line(
    tmp_path: Path,
) -> None:
    """The limits are options so a manual run can tighten them."""
    assert (
        __main__.main(
            [
                "--pr-number",
                "42",
                "--output",
                str(tmp_path),
                "--max-changed-lines",
                "10",
            ]
        )
        == 0
    )

    assert json.loads((tmp_path / "results.json").read_text())["too_long"] is True


def test_requires_a_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without a token no GitHub call can be made."""
    monkeypatch.delenv("GITHUB_TOKEN")

    with pytest.raises(SystemExit):
        __main__.main(["--pr-number", "42", "--output", str(tmp_path)])


def test_requires_a_repository(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without a repository the pull request cannot be located."""
    monkeypatch.delenv("GITHUB_REPOSITORY")

    with pytest.raises(SystemExit):
        __main__.main(["--pr-number", "42", "--output", str(tmp_path)])
