"""Test the sync_custom_integrations script."""

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from script import sync_custom_integrations
from script.sync_custom_integrations import (
    LOCK_FILE,
    STATE_FORMAT,
    GitError,
    UnsafePathError,
    _content_in_root,
    download,
    ensure_ignored,
    fetch_heads,
    git_env,
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


def test_prune_skips_files_and_symlinks(tmp_path: Path) -> None:
    """Test that files and symlinks next to repos are skipped, not removed."""
    copy = tmp_path / "copy"
    (copy / "owner" / "gone").mkdir(parents=True)
    (copy / "owner" / ".DS_Store").write_text("")
    (tmp_path / "outside").mkdir()
    (copy / "owner" / "link").symlink_to(tmp_path / "outside")

    removed = prune(copy, set())

    assert removed == ["owner/gone"]
    assert (copy / "owner" / ".DS_Store").is_file()
    assert (copy / "owner" / "link").is_symlink()
    assert (tmp_path / "outside").is_dir()


@pytest.mark.parametrize(
    ("dest", "lookalike"),
    [
        pytest.param("sources[1]", "sources1", id="brackets"),
        pytest.param("a*b?", "axxbx", id="wildcards"),
    ],
)
def test_ensure_ignored_escapes_and_keeps_own_line(
    tmp_path: Path, dest: str, lookalike: str
) -> None:
    """Test the exclude rule matches only the destination, on its own line."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    exclude = tmp_path / ".git" / "info" / "exclude"
    exclude.write_text("existing-rule")
    (tmp_path / dest).mkdir()
    (tmp_path / lookalike).mkdir()

    ensure_ignored(tmp_path / dest)

    def ignored(name: str) -> bool:
        return (
            subprocess.run(
                ["git", "-C", str(tmp_path), "check-ignore", "-q", f"{name}/x"],
                check=False,
            ).returncode
            == 0
        )

    assert ignored(dest)
    assert not ignored(lookalike)
    assert exclude.read_text().splitlines()[0] == "existing-rule"


def test_interrupted_update_leaves_repos_unrecorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that an interrupted run never pairs updated files with an old SHA."""
    for repo in ("a/one", "b/two"):
        (tmp_path / repo / ".git").mkdir(parents=True)
    save_state(tmp_path, {"a/one": "1" * 40, "b/two": "1" * 40}, None)
    monkeypatch.setattr(
        sync_custom_integrations,
        "_get",
        Mock(return_value=json.dumps(["a/one", "b/two"]).encode()),
    )
    monkeypatch.setattr(sync_custom_integrations, "_token", Mock(return_value="t"))
    monkeypatch.setattr(
        sync_custom_integrations,
        "fetch_heads",
        Mock(return_value={"a/one": "2" * 40, "b/two": "2" * 40}),
    )
    monkeypatch.setattr(sync_custom_integrations, "ensure_ignored", Mock())
    # The first repo is updated in place, then the run is interrupted
    download = Mock(side_effect=[None, KeyboardInterrupt])
    monkeypatch.setattr(sync_custom_integrations, "download", download)
    monkeypatch.setattr(
        sys, "argv", ["sync", "--dest", str(tmp_path), "--workers", "1"]
    )

    with pytest.raises(KeyboardInterrupt):
        sync_custom_integrations.main()

    assert download.call_count == 2
    assert load_state(tmp_path) == ({}, None)


@pytest.mark.parametrize(
    ("link", "target"),
    [
        pytest.param("owner", ".", id="owner_symlink"),
        pytest.param("owner/repo", "repo", id="repo_symlink"),
    ],
)
def test_download_refuses_symlinked_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link: str, target: str
) -> None:
    """Test that a symlinked owner or repo directory is never updated through."""
    copy = tmp_path / "copy"
    outside = tmp_path / "outside"
    (outside / "repo" / ".git").mkdir(parents=True)
    (copy / link).parent.mkdir(parents=True)
    (copy / link).symlink_to(outside / target)
    git = Mock()
    monkeypatch.setattr(sync_custom_integrations, "_git", git)

    with pytest.raises(UnsafePathError):
        download(copy, "owner/repo", "2" * 40)

    git.assert_not_called()
    assert (outside / "repo" / ".git").is_dir()


def test_targeted_removal_skips_symlinked_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that removing an unavailable repo never deletes through a symlink."""
    copy = tmp_path / "copy"
    copy.mkdir()
    outside = tmp_path / "outside"
    (outside / "repo" / ".git").mkdir(parents=True)
    (copy / "owner").symlink_to(outside)
    save_state(copy, {"owner/repo": "1" * 40}, None)
    monkeypatch.setattr(
        sync_custom_integrations,
        "_get",
        Mock(return_value=json.dumps(["owner/repo"]).encode()),
    )
    monkeypatch.setattr(sync_custom_integrations, "_token", Mock(return_value="t"))
    monkeypatch.setattr(
        sync_custom_integrations, "fetch_heads", Mock(return_value={"owner/repo": None})
    )
    monkeypatch.setattr(sync_custom_integrations, "ensure_ignored", Mock())
    monkeypatch.setattr(sys, "argv", ["sync", "--dest", str(copy), "owner/repo"])

    sync_custom_integrations.main()

    assert (outside / "repo" / ".git").is_dir()
    assert load_state(copy) == ({}, None)


def test_fetch_heads_treats_private_repos_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that private, missing and empty repos have no SHA."""
    sha = {"target": {"oid": "a" * 40}}
    response = {
        "data": {
            "r0": {"isPrivate": False, "defaultBranchRef": sha},
            "r1": {"isPrivate": True, "defaultBranchRef": sha},
            "r2": None,
            "r3": {"isPrivate": False, "defaultBranchRef": None},
        },
        "errors": [{"type": "NOT_FOUND", "path": ["r2"]}],
    }
    monkeypatch.setattr(
        sync_custom_integrations, "_get", Mock(return_value=json.dumps(response))
    )

    assert fetch_heads(["o/public", "o/private", "o/gone", "o/empty"], "t") == {
        "o/public": "a" * 40,
        "o/private": None,
        "o/gone": None,
        "o/empty": None,
    }


@pytest.mark.parametrize(
    ("git_results", "expected"),
    [
        pytest.param([""], False, id="no_hacs_json"),
        pytest.param(["hacs.json\n", "not json"], False, id="invalid_json"),
        pytest.param(["hacs.json\n", "{}"], False, id="flag_unset"),
        pytest.param(["hacs.json\n", '{"content_in_root": true}'], True, id="flag_set"),
    ],
)
def test_content_in_root(
    monkeypatch: pytest.MonkeyPatch, git_results: list[str], expected: bool
) -> None:
    """Test reading the content_in_root flag from hacs.json."""
    monkeypatch.setattr(sync_custom_integrations, "_git", Mock(side_effect=git_results))

    assert _content_in_root(Path("repo"), "a" * 40) is expected


def test_content_in_root_read_failure_fails_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a failed read of an existing hacs.json is not taken as no flag."""
    monkeypatch.setattr(
        sync_custom_integrations,
        "_git",
        Mock(side_effect=["hacs.json\n", GitError("show", "network error")]),
    )

    with pytest.raises(GitError):
        _content_in_root(Path("repo"), "a" * 40)


def test_unchanged_symlinked_repo_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that a symlinked repo is rejected even when its SHA is unchanged."""
    copy = tmp_path / "copy"
    (copy / "owner").mkdir(parents=True)
    outside = tmp_path / "outside"
    (outside / ".git").mkdir(parents=True)
    (copy / "owner" / "repo").symlink_to(outside)
    save_state(copy, {"owner/repo": "1" * 40}, None)
    monkeypatch.setattr(
        sync_custom_integrations,
        "_get",
        Mock(return_value=json.dumps(["owner/repo"]).encode()),
    )
    monkeypatch.setattr(sync_custom_integrations, "_token", Mock(return_value="t"))
    monkeypatch.setattr(
        sync_custom_integrations,
        "fetch_heads",
        Mock(return_value={"owner/repo": "1" * 40}),
    )
    monkeypatch.setattr(sync_custom_integrations, "ensure_ignored", Mock())
    git = Mock()
    monkeypatch.setattr(sync_custom_integrations, "_git", git)
    monkeypatch.setattr(sys, "argv", ["sync", "--dest", str(copy), "owner/repo"])

    with pytest.raises(SystemExit) as exc_info:
        sync_custom_integrations.main()

    assert exc_info.value.code == sync_custom_integrations.EXIT_PARTIAL
    git.assert_not_called()
    assert load_state(copy) == ({}, None)
    assert (outside / ".git").is_dir()


def test_git_env_drops_askpass_helpers() -> None:
    """Test that inherited askpass helpers never reach git."""
    env = git_env(
        {"PATH": "/usr/bin", "GIT_ASKPASS": "/ide/askpass.sh", "SSH_ASKPASS": "x"}
    )

    assert env["PATH"] == "/usr/bin"
    assert "GIT_ASKPASS" not in env
    assert "SSH_ASKPASS" not in env
    assert env["GIT_TERMINAL_PROMPT"] == "0"
