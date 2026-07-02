"""Tests for the translation download script."""

import json
from pathlib import Path

import pytest

from script.translations import download


def test_run_sources_english_from_strings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The build replaces the Lokalise English with the checkout's strings.json.

    English is the source of truth in strings.json, so a release build must ship
    it rather than the dev-sourced English the single Lokalise project tracks.
    """
    monkeypatch.setattr(download, "DOWNLOAD_DIR", tmp_path)

    def _fake_docker() -> None:
        # Lokalise serves dev-sourced English, here with a drifted placeholder.
        download.save_json(tmp_path / "en.json", {"component": {"x": {"t": "{name}"}}})

    strings_english = {"component": {"x": {"t": "{site}"}}}
    monkeypatch.setattr(download, "run_download_docker", _fake_docker)
    monkeypatch.setattr(download, "generate_upload_data", lambda: strings_english)
    monkeypatch.setattr(download, "delete_old_translations", lambda: None)
    monkeypatch.setattr(download, "save_integrations_translations", lambda: None)

    download.run()

    assert json.loads((tmp_path / "en.json").read_text()) == strings_english
