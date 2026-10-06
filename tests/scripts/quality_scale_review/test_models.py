"""Tests for script.quality_scale_review.models."""

import pytest

from script.quality_scale_review.models import PullRequest, Results, RuleDoc


def _pull_request(**overrides: object) -> PullRequest:
    """Return a pull request with every field set."""
    fields: dict = {
        "number": 42,
        "title": "Add peblar sensors",
        "body": "Body text",
        "head_sha": "abc123",
        "base_ref": "dev",
        "additions": 30,
        "deletions": 12,
        "changed_files": 3,
        "file_statuses": {"homeassistant/components/peblar/sensor.py": "modified"},
    }
    return PullRequest(**(fields | overrides))


def test_changed_lines_sums_additions_and_deletions() -> None:
    """Additions and deletions add up to the changed line count."""
    assert _pull_request(additions=30, deletions=12).changed_lines == 42


def test_to_meta_dict_omits_the_changed_filenames() -> None:
    """The metadata payload holds exactly the keys the agent reads."""
    assert _pull_request().to_meta_dict() == {
        "number": 42,
        "title": "Add peblar sensors",
        "body": "Body text",
        "headRefOid": "abc123",
        "baseRefName": "dev",
        "additions": 30,
        "deletions": 12,
        "changedFiles": 3,
    }


def test_rule_doc_rule_drops_the_extension() -> None:
    """The rule id is the documentation file name without its extension."""
    assert RuleDoc(filename="config-flow.md", text="").rule == "config-flow"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param('---\ntitle: "Config flow"\n---\n', "Config flow", id="quoted"),
        pytest.param("---\ntitle: Config flow\n---\n", "Config flow", id="unquoted"),
        pytest.param("---\nrelated: config-flow\n---\n", "", id="missing"),
        pytest.param("# title: not frontmatter\n", "", id="not-at-line-start"),
    ],
)
def test_rule_doc_title(text: str, expected: str) -> None:
    """The title comes from the frontmatter, quoted or not."""
    assert RuleDoc(filename="config-flow.md", text=text).title == expected


def test_results_to_dict() -> None:
    """The results payload holds exactly the keys the agentic stage reads."""
    results = Results(
        pr_number=42,
        head_sha="abc123",
        skip=True,
        too_long=True,
        skip_reason="changes too much",
        changed_lines=9000,
        changed_files=400,
        domains=["peblar"],
    )
    assert results.to_dict() == {
        "pr_number": 42,
        "head_sha": "abc123",
        "skip": True,
        "too_long": True,
        "skip_reason": "changes too much",
        "changed_lines": 9000,
        "changed_files": 400,
        "domains": ["peblar"],
    }
