"""Tests for script.quality_scale_review.artifact."""

import json
from pathlib import Path

from script.quality_scale_review import artifact
from script.quality_scale_review.models import PullRequest, Results, RuleDoc

_PR = PullRequest(
    number=42,
    title="Add peblar sensors",
    body="Body text",
    head_sha="abc123",
    base_ref="dev",
    additions=30,
    deletions=12,
    changed_files=3,
    file_statuses={"homeassistant/components/peblar/sensor.py": "modified"},
)
_RESULTS = Results(
    pr_number=42,
    head_sha="abc123",
    skip=False,
    too_long=False,
    skip_reason="",
    changed_lines=42,
    changed_files=3,
    domains=["adax", "peblar"],
)


def test_write_pull_request_creates_the_output_directory(tmp_path: Path) -> None:
    """The artifact directory does not have to exist beforehand."""
    output = tmp_path / "deterministic"

    artifact.write_pull_request(output, _RESULTS, _PR)

    assert json.loads((output / "results.json").read_text()) == _RESULTS.to_dict()
    assert json.loads((output / "pr-meta.json").read_text()) == _PR.to_meta_dict()
    assert (output / "domains.txt").read_text() == "adax\npeblar\n"


def test_domains_file_is_empty_without_domains(tmp_path: Path) -> None:
    """No domain means an empty file, not a blank line."""
    results = Results(
        pr_number=42,
        head_sha="abc123",
        skip=True,
        too_long=False,
        skip_reason="touches no integration with a quality_scale.yaml",
        changed_lines=42,
        changed_files=3,
        domains=[],
    )

    artifact.write_pull_request(tmp_path, results, _PR)

    assert (tmp_path / "domains.txt").read_text() == ""


def test_write_diff(tmp_path: Path) -> None:
    """The diff is written verbatim."""
    artifact.write_diff(tmp_path, "diff --git a/x b/x\n")

    assert (tmp_path / "pr-diff.patch").read_text() == "diff --git a/x b/x\n"


def test_write_rules(tmp_path: Path) -> None:
    """The index and one file per rule page are written."""
    artifact.write_rules(
        tmp_path,
        "# Integration Quality Scale rules: tier | rule | title\n",
        [RuleDoc("config-flow.md", "Config flow page")],
    )

    assert (tmp_path / "rules-index.txt").read_text().startswith("# Integration")
    assert (tmp_path / "rules" / "config-flow.md").read_text() == "Config flow page"
