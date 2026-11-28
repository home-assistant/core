"""Fixtures for the PR reviewer workflow script tests."""

from pathlib import Path
import subprocess

import pytest

from . import FakeGh

REPO = "home-assistant/core"


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGh:
    """Fake the `gh api` requests of the scripts, in GITHUB_REPOSITORY."""
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    fake = FakeGh(REPO)
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


@pytest.fixture
def github_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return the GITHUB_OUTPUT file, which does not exist yet."""
    path = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    return path
