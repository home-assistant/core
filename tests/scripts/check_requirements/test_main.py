"""Tests for script.check_requirements.__main__ (CLI entry point)."""

import json
from pathlib import Path

import pytest

from script.check_requirements import __main__ as main_mod
from script.check_requirements.pypi import ProvenanceResult, PypiPackageInfo


def test_main_writes_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI parses args, runs checks, and writes a JSON artifact."""
    diff_file = tmp_path / "diff.patch"
    diff_file.write_text(
        "diff --git a/requirements_all.txt b/requirements_all.txt\n"
        "--- a/requirements_all.txt\n"
        "+++ b/requirements_all.txt\n"
        "@@ -1 +1 @@\n"
        "-pkg==1.0.0\n"
        "+pkg==1.1.0\n",
        encoding="utf-8",
    )
    output_file = tmp_path / "results.json"

    monkeypatch.setattr(
        "script.check_requirements.runner.fetch_package_info",
        lambda name, version: PypiPackageInfo(
            project_urls={"Source": "https://github.com/example/pkg"},
            repo_url="https://github.com/example/pkg",
            file_provenance_urls=["whatever"],
            found=True,
        ),
    )
    monkeypatch.setattr(
        "script.check_requirements.runner.check_provenance",
        lambda info: ProvenanceResult(
            has_attestation=True,
            publisher_kind="GitHub",
            recognized_publisher=True,
            detail="ok",
        ),
    )

    exit_code = main_mod.main(
        [
            "--pr-number",
            "42",
            "--diff",
            str(diff_file),
            "--output",
            str(output_file),
        ]
    )
    assert exit_code == 0

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["pr_number"] == 42
    assert payload["packages"][0]["name"] == "pkg"

    captured = capsys.readouterr()
    assert "check_requirements: 1 package change(s)" in captured.err


def test_main_missing_diff_file_exits(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing --diff file triggers argparse's error path (SystemExit)."""
    output_file = tmp_path / "results.json"
    missing_diff = tmp_path / "does-not-exist.patch"

    with pytest.raises(SystemExit) as excinfo:
        main_mod.main(
            [
                "--pr-number",
                "1",
                "--diff",
                str(missing_diff),
                "--output",
                str(output_file),
            ]
        )
    assert excinfo.value.code == 2  # argparse error exit
    captured = capsys.readouterr()
    assert "not found" in captured.err
