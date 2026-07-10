"""Tests for script.check_requirements.__main__ (CLI entry point)."""

import json
from pathlib import Path

import pytest

from script.check_requirements import __main__ as main_mod
from script.check_requirements.gate import GateDecision
from script.check_requirements.pypi import ProvenanceResult, PypiPackageInfo

_SHA = "abc1234def5678abc1234def5678abc1234def56"


def _write_bump_diff(path: Path) -> None:
    path.write_text(
        "diff --git a/requirements_all.txt b/requirements_all.txt\n"
        "--- a/requirements_all.txt\n"
        "+++ b/requirements_all.txt\n"
        "@@ -1 +1 @@\n"
        "-pkg==1.0.0\n"
        "+pkg==1.1.0\n",
        encoding="utf-8",
    )


def _mock_pypi(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_main_writes_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the gate runs the checks, the CLI writes a non-skipped artifact."""
    diff_file = tmp_path / "diff.patch"
    _write_bump_diff(diff_file)
    output_file = tmp_path / "results.json"
    monkeypatch.setattr(
        main_mod, "_resolve_skip", lambda pr, sha: GateDecision(False, "running checks")
    )
    _mock_pypi(monkeypatch)

    exit_code = main_mod.main(
        [
            "--pr-number",
            "42",
            "--head-sha",
            _SHA,
            "--diff",
            str(diff_file),
            "--output",
            str(output_file),
        ]
    )
    assert exit_code == 0

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["skip_aw"] is False
    assert payload["pr_number"] == 42
    assert payload["head_sha"] == _SHA
    assert payload["packages"][0]["name"] == "pkg"
    assert (
        f"https://github.com/home-assistant/core/commit/{_SHA}"
        in payload["rendered_comment"]
    )
    assert "check_requirements: 1 package change(s)" in capsys.readouterr().err


def test_main_skips_but_still_writes_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the gate skips, no checks run but a skip-flagged artifact is written."""
    diff_file = tmp_path / "diff.patch"
    _write_bump_diff(diff_file)
    output_file = tmp_path / "results.json"
    monkeypatch.setattr(
        main_mod, "_resolve_skip", lambda pr, sha: GateDecision(True, "nothing changed")
    )

    # The checks must not run when skipping; make them explode if they do.
    def _boom(name: str, version: str) -> None:
        raise AssertionError("checks must not run when the gate skips")

    monkeypatch.setattr("script.check_requirements.runner.fetch_package_info", _boom)

    exit_code = main_mod.main(
        [
            "--pr-number",
            "42",
            "--head-sha",
            _SHA,
            "--diff",
            str(diff_file),
            "--output",
            str(output_file),
        ]
    )
    assert exit_code == 0
    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload == {
        "version": 1,
        "pr_number": 42,
        "skip_aw": True,
        "head_sha": _SHA,
        "needs_agent": False,
        "packages": [],
        "rendered_comment": "",
    }


def test_resolve_skip_without_credentials_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing repo/token falls open (runs) without ever calling the gate."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("decide_skip must not be called without credentials")

    monkeypatch.setattr(main_mod, "decide_skip", _boom)
    assert main_mod._resolve_skip(42, _SHA).skip is False


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
