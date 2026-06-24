"""Tests for the translation download script."""

import json
from pathlib import Path

import pytest

from script.translations import download
from script.translations.download import _placeholder_names, filter_translations


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("no placeholders", set()),
        ("{name} ({host})", {"name", "host"}),
        ("{name:>10}", {"name"}),
        # ICU / non str.format strings impose no constraint instead of raising.
        ("{count, plural, one {x} other {y}}", set()),
    ],
)
def test_placeholder_names(value: str, expected: set[str]) -> None:
    """Placeholder names are extracted, malformed strings yield no constraint."""
    assert _placeholder_names(value) == expected


def test_filter_translations_drops_keys_missing_from_strings() -> None:
    """A translation key absent from the strings is removed."""
    translations = {"title": "Title", "stale": "Gone"}
    filter_translations(translations, {"title": "Title"})
    assert translations == {"title": "Title"}


def test_filter_translations_drops_incompatible_placeholder() -> None:
    """A translation referencing an undefined placeholder is dropped.

    Guards the release-pipeline case where the branch strings.json still uses
    the old placeholder while the downloaded translation uses a renamed one.
    """
    translations = {"config": {"flow_title": "{name} ({host})", "kept": "{host}"}}
    strings = {"config": {"flow_title": "{site} ({host})", "kept": "{host}"}}
    filter_translations(translations, strings)
    assert translations == {"config": {"kept": "{host}"}}


@pytest.mark.parametrize(
    ("value", "source"),
    [
        ("{name} ({host})", "{name} ({host})"),
        # A subset of the source placeholders is allowed.
        ("{host}", "{name} ({host})"),
        ("plain", "{name}"),
    ],
)
def test_filter_translations_keeps_compatible_placeholders(
    value: str, source: str
) -> None:
    """Translations whose placeholders the source defines are kept."""
    translations = {"flow_title": value}
    filter_translations(translations, {"flow_title": source})
    assert translations == {"flow_title": value}


def test_filter_translations_prunes_emptied_branches() -> None:
    """A dict left empty after filtering is removed."""
    translations = {"config": {"flow_title": "{name}"}}
    filter_translations(translations, {"config": {"flow_title": "{site}"}})
    assert translations == {}


def test_filter_translations_drops_dict_over_non_dict_source() -> None:
    """A nested translation whose source is not a dict is removed."""
    translations = {"config": {"nested": "value"}}
    filter_translations(translations, {"config": "scalar"})
    assert translations == {}


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
