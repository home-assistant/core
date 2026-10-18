"""Test the sync_custom_integrations script."""

import json
from pathlib import Path

import pytest

from script.sync_custom_integrations import (
    LOCK_FILE,
    STATE_FORMAT,
    is_repo_slug,
    load_state,
    prune,
    save_state,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("owner/repo", True, id="plain"),
        pytest.param("my-org/ha.repo_name-2", True, id="allowed_characters"),
        pytest.param("../victim", False, id="parent_traversal"),
        pytest.param("owner/..", False, id="dotdot_repo"),
        pytest.param("owner/.", False, id="dot_repo"),
        pytest.param("owner/repo/extra", False, id="extra_segment"),
        pytest.param("/owner/repo", False, id="absolute"),
        pytest.param("owner", False, id="no_repo"),
        pytest.param("own.er/repo", False, id="dot_in_owner"),
        pytest.param("owner/re po", False, id="space"),
        pytest.param("", False, id="empty"),
    ],
)
def test_is_repo_slug(value: str, expected: bool) -> None:
    """Test that only plain owner/repo slugs are accepted."""
    assert is_repo_slug(value) is expected


def test_load_state_missing_or_empty(tmp_path: Path) -> None:
    """Test that an empty directory, or one with only the lock, is accepted."""
    assert load_state(tmp_path) == ({}, None)
    (tmp_path / LOCK_FILE).touch()
    assert load_state(tmp_path) == ({}, None)


def test_load_state_refuses_without_state_file(tmp_path: Path) -> None:
    """Test that a populated directory without a state file is refused."""
    (tmp_path / "someone" / "data").mkdir(parents=True)

    with pytest.raises(SystemExit):
        load_state(tmp_path)


@pytest.mark.parametrize(
    "state_text",
    [
        pytest.param("not json", id="invalid_json"),
        pytest.param(json.dumps([1, 2]), id="not_an_object"),
        pytest.param(json.dumps({"owner/repo": "sha"}), id="unmarked_flat_map"),
        pytest.param(json.dumps({"format": "other/1", "repos": {}}), id="wrong_format"),
        pytest.param(
            json.dumps({"format": STATE_FORMAT, "repos": []}), id="repos_not_a_map"
        ),
        pytest.param(
            json.dumps({"format": STATE_FORMAT, "repos": {"owner/repo": 1}}),
            id="sha_not_a_string",
        ),
        pytest.param(
            json.dumps({"format": STATE_FORMAT, "repos": {}, "synced_at": 1}),
            id="synced_at_not_a_string",
        ),
    ],
)
def test_load_state_refuses_invalid_state(tmp_path: Path, state_text: str) -> None:
    """Test that a populated directory with an invalid state file is refused."""
    (tmp_path / "someone" / "data").mkdir(parents=True)
    (tmp_path / ".state.json").write_text(state_text)

    with pytest.raises(SystemExit):
        load_state(tmp_path)


def test_save_and_load_state(tmp_path: Path) -> None:
    """Test that the state and synced_at round-trip, and synced_at is optional."""
    save_state(tmp_path, {"owner/repo": "a" * 40}, "2026-10-18T00:00:00+00:00")
    assert load_state(tmp_path) == (
        {"owner/repo": "a" * 40},
        "2026-10-18T00:00:00+00:00",
    )

    save_state(tmp_path, {"owner/repo": "b" * 40}, None)
    assert "synced_at" not in json.loads((tmp_path / ".state.json").read_text())
    assert load_state(tmp_path) == ({"owner/repo": "b" * 40}, None)


def test_prune(tmp_path: Path) -> None:
    """Test that only unwanted repos and emptied owners are removed."""
    for repo in ("keep/one", "keep/gone", "drop/gone"):
        (tmp_path / repo / "custom_components").mkdir(parents=True)
    (tmp_path / ".hidden" / "dir").mkdir(parents=True)
    (tmp_path / ".state.json").write_text("{}")

    removed = prune(tmp_path, {"keep/one"})

    assert sorted(removed) == ["drop/gone", "keep/gone"]
    assert (tmp_path / "keep" / "one" / "custom_components").is_dir()
    assert not (tmp_path / "keep" / "gone").exists()
    assert not (tmp_path / "drop").exists()
    assert (tmp_path / ".hidden" / "dir").is_dir()
    assert (tmp_path / ".state.json").is_file()
