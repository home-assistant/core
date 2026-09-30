"""Tests for the Marketplace utilities."""

import asyncio
from pathlib import Path
from unittest.mock import patch

from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel
import pytest

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.enums import RepositoryFile
from homeassistant.components.marketplace.exceptions import MarketplaceError
from homeassistant.components.marketplace.repositories.base import Repository
from homeassistant.components.marketplace.utils import filters, path, regex, version
from homeassistant.components.marketplace.utils.decorator import (
    concurrent,
    return_none_on_exception,
)
from homeassistant.components.marketplace.utils.tree import (
    tree_entry_directory,
    tree_entry_filename,
    tree_entry_is_directory,
)
from homeassistant.components.marketplace.utils.url import (
    github_archive,
    github_raw_file,
    github_release_asset,
    ref_version,
)


def _tree_file(full_path: str, *, directory: bool = False) -> GitHubGitTreeEntryModel:
    """Return a tree entry for the given path."""
    return GitHubGitTreeEntryModel(
        {"path": full_path, "type": "tree" if directory else "blob"}
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/user/repo", "user/repo"),
        ("user/repo/", "user/repo"),
        ("user/repo", "user/repo"),
        ("USER/REPO", "user/repo"),
        ("user/repo.git", "user/repo"),
        ("user/repo.repo", "user/repo.repo"),
        ("git@github.com:user/repo.git", "user/repo"),
        ("https://google.com/user/repo", None),
    ],
)
def test_extract_repository_from_url(url: str, expected: str | None) -> None:
    """Test extracting the owner/repo part from all the shapes users paste."""
    assert regex.extract_repository_from_url(url) == expected


def test_github_release_asset() -> None:
    """Test the download URL of a release asset."""
    assert (
        github_release_asset(
            repository="owner/repo", version="1.0.0", filename="example.zip"
        )
        == "https://github.com/owner/repo/releases/download/1.0.0/example.zip"
    )


@pytest.mark.parametrize(
    ("version_string", "variant", "expected"),
    [
        pytest.param(
            "1.0.0",
            "heads",
            "https://github.com/owner/repo/archive/refs/heads/1.0.0.zip",
            id="branch",
        ),
        pytest.param(
            "1.0.0",
            "tags",
            "https://github.com/owner/repo/archive/refs/tags/1.0.0.zip",
            id="tag",
        ),
        pytest.param(
            "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
            "heads",
            "https://github.com/owner/repo/archive/1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b.zip",
            id="sha-heads",
        ),
        pytest.param(
            "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
            "tags",
            "https://github.com/owner/repo/archive/1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b.zip",
            id="sha-tags",
        ),
    ],
)
def test_github_archive(version_string: str, variant: str, expected: str) -> None:
    """Test the download URL of a repository archive."""
    assert (
        github_archive(repository="owner/repo", version=version_string, variant=variant)
        == expected
    )


async def test_is_safe(marketplace: MarketplaceManager) -> None:
    """Test that the directories the Marketplace manages are never removable."""
    config_path = marketplace.core.config_path
    configuration = marketplace.configuration

    assert path.is_safe(marketplace, "/test")
    assert not path.is_safe(marketplace, f"{config_path}/{configuration.plugin_path}")
    assert not path.is_safe(marketplace, f"{config_path}/python_scripts")
    assert not path.is_safe(marketplace, f"{config_path}/{configuration.theme_path}/")
    assert not path.is_safe(marketplace, f"{config_path}/custom_components/")
    assert not path.is_safe(marketplace, f"{config_path}/custom_components")
    assert not path.is_safe(marketplace, f"{config_path}/custom_templates")
    assert not path.is_safe(marketplace, config_path)
    assert not path.is_safe(marketplace, f"{config_path}/.storage")

    # A path that walks back out of a managed directory is the same directory
    assert not path.is_safe(marketplace, f"{config_path}/custom_components/example/..")


@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param("example.js", id="file"),
        pytest.param("nested/example.js", id="nested_file"),
        pytest.param("nested/../example.js", id="normalized_file"),
        pytest.param("", id="the_directory_itself"),
    ],
)
def test_resolve_in_directory(tmp_path: Path, candidate: str) -> None:
    """Test the paths that are inside the target directory."""
    resolved = path.resolve_in_directory(tmp_path, candidate)

    assert resolved == (tmp_path / candidate).resolve()


@pytest.mark.parametrize(
    "candidate",
    [
        pytest.param("../escaped.js", id="parent"),
        pytest.param("nested/../../escaped.js", id="parent_from_nested"),
        pytest.param("/etc/passwd", id="absolute"),
        pytest.param("..", id="the_parent_itself"),
    ],
)
def test_resolve_in_directory_rejects_escapes(tmp_path: Path, candidate: str) -> None:
    """Test that a path leaving the target directory is refused."""
    with pytest.raises(MarketplaceError, match="is not inside"):
        path.resolve_in_directory(tmp_path, candidate)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("1.0.0", "0.9.9", True),
        ("1", "0.9.9", True),
        ("1.1", "0.9.9", True),
        ("0.10.0", "0.9.9", True),
        ("0.0.10", "0.9.9", False),
        ("0.9.0", "0.9.9", False),
        ("1.0.0", "1.0.0", True),
        ("1.0.0b1", "1.0.0b0", True),
        ("1.0.0b1", "1.0.0", False),
        ("1.0.0", "1.0.0b1", True),
        ("1.0.0rc1", "1.0.0b1", True),
        ("1.0.0a1", "1.0.0b1", False),
        ("1.0.0", "1.0.0a0", True),
        ("1.0.0", "1.0.0b0", True),
        ("1.0.0", "1.0.0rc0", True),
        ("0", "1.0.0rc0", False),
        ("", "1.0", False),
    ],
)
def test_is_same_or_newer_version(left: str, right: str, expected: bool) -> None:
    """Test comparing two version strings."""
    assert version.is_same_or_newer_version(left, right) is expected


@pytest.mark.parametrize(
    ("default_branch", "last_version", "selected_tag", "expected"),
    [
        pytest.param("main", None, "main", "main", id="selected-default-branch"),
        pytest.param(None, None, None, "main", id="nothing-known"),
        pytest.param("main", None, "2", "2", id="selected-published-tag"),
        pytest.param("main", "3", None, "3", id="last-version"),
        pytest.param("main", None, None, "main", id="default-branch"),
        pytest.param("dev", None, None, "dev", id="other-default-branch"),
        pytest.param("main", "2", "main", "main", id="selected-tag-wins"),
        pytest.param("main", None, "9", "main", id="unpublished-tag-falls-back"),
    ],
)
def test_version_to_install(
    mock_repository: Repository,
    default_branch: str | None,
    last_version: str | None,
    selected_tag: str | None,
    expected: str,
) -> None:
    """Test which version the Marketplace picks to install."""
    mock_repository.data.default_branch = default_branch
    mock_repository.data.last_version = last_version
    mock_repository.data.selected_tag = selected_tag

    assert mock_repository.version_to_install() == expected


def test_version_to_install_clears_redundant_selected_tag(
    mock_repository: Repository,
) -> None:
    """Test that selecting the latest version stops pinning the repository."""
    mock_repository.data.last_version = "3"
    mock_repository.data.selected_tag = "3"

    assert mock_repository.version_to_install() == "3"
    assert mock_repository.data.selected_tag is None


def test_version_to_install_forced_branch(mock_repository: Repository) -> None:
    """Test that a forced branch overrules everything else."""
    mock_repository.ref = "my-ref"
    assert mock_repository.version_to_install() == "3"

    mock_repository.force_branch = True
    assert mock_repository.version_to_install() == "my-ref"


def test_get_first_directory_in_directory() -> None:
    """Test finding the first subdirectory of a directory."""
    tree = [
        _tree_file("test", directory=True),
        _tree_file("test/path", directory=True),
        _tree_file("test/path/sub", directory=True),
    ]

    assert filters.get_first_directory_in_directory(tree, "test") == "path"


def test_get_first_directory_in_directory_not_found() -> None:
    """Test that an unrelated tree yields no subdirectory."""
    tree = [_tree_file(".github/path/file.file", directory=True)]

    assert filters.get_first_directory_in_directory(tree, "test") is None


@pytest.mark.parametrize(
    ("full_path", "expected_path", "expected_filename"),
    [
        pytest.param("example.js", "", "example.js", id="root"),
        pytest.param("dist/example.js", "dist", "example.js", id="subdirectory"),
        pytest.param(
            "dist/nested/example.js", "dist/nested", "example.js", id="nested"
        ),
    ],
)
def test_tree_entry(full_path: str, expected_path: str, expected_filename: str) -> None:
    """Test the directory and filename a tree entry is split into."""
    entry = _tree_file(full_path)

    assert tree_entry_directory(entry) == expected_path
    assert tree_entry_filename(entry) == expected_filename
    assert not tree_entry_is_directory(entry)
    assert (
        github_raw_file(repository="test/test", ref="main", path=full_path)
        == f"https://raw.githubusercontent.com/test/test/main/{full_path}"
    )


async def test_concurrent_limits_running_calls() -> None:
    """Test the decorator caps how many calls run at once, without sleeping."""
    running = 0
    peak = 0
    release = asyncio.Event()

    @concurrent(concurrenttasks=2)
    async def update_something() -> str:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await release.wait()
        running -= 1
        return "done"

    with patch("asyncio.sleep") as sleep_mock:
        tasks = [asyncio.create_task(update_something()) for _ in range(5)]
        await asyncio.wait(tasks, timeout=0.1)
        assert running == 2

        release.set()
        assert await asyncio.gather(*tasks) == ["done"] * 5

    assert peak == 2
    assert not sleep_mock.called


async def test_return_none_on_exception_async_function() -> None:
    """Test an asynchronous function."""

    @return_none_on_exception
    async def returns_value() -> str:
        return "test_value"

    @return_none_on_exception
    async def raises() -> str:
        raise ValueError("Test exception")

    assert await returns_value() == "test_value"
    assert await raises() is None


async def test_return_none_on_exception_methods() -> None:
    """Test a method, with and without its optional argument."""

    class Example:
        """Example class with a decorated method."""

        @return_none_on_exception
        async def async_method(self, arg1: str, arg2: str | None = None) -> str:
            """Return the joined arguments, or raise without the second one."""
            if arg2 is None:
                raise ValueError("Test exception")
            return f"{arg1}_{arg2}"

    example = Example()

    assert await example.async_method("test", "value") == "test_value"
    assert await example.async_method("test") is None


def test_repository_file_enum() -> None:
    """Test that the repository file names render as plain strings."""
    assert RepositoryFile.REPOSITORY_MANIFEST == "hacs.json"
    assert RepositoryFile.REPOSITORY_MANIFEST.value == "hacs.json"
    assert str(RepositoryFile.REPOSITORY_MANIFEST) == "hacs.json"


@pytest.mark.parametrize(
    ("ref", "version"),
    [
        pytest.param("tags/1.0.0", "1.0.0", id="tag"),
        pytest.param("main", "main", id="branch"),
        pytest.param("fix-tags/one", "fix-tags/one", id="tags_inside_a_branch"),
        pytest.param(None, "", id="none"),
    ],
)
def test_ref_version(ref: str | None, version: str) -> None:
    """Test only the prefix of a tag ref is removed."""
    assert ref_version(ref) == version
