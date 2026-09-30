"""Tests for the Marketplace repositories."""

from collections.abc import AsyncIterator
from http import HTTPStatus
import io
import json
from pathlib import Path
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import zipfile

from aiogithubapi import GitHubAuthenticationException, GitHubReleaseAssetModel
from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel
from aiogithubapi.models.release import GitHubReleaseModel
from awesomeversion import AwesomeVersion
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from yarl import URL

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.components.marketplace.base import (
    MarketplaceManager,
    RemovedRepository,
)
from homeassistant.components.marketplace.const import DOMAIN, MAX_DOWNLOAD_SIZE
from homeassistant.components.marketplace.enums import (
    DisabledReason,
    MarketplaceSignal,
    RepositoryCategory,
)
from homeassistant.components.marketplace.exceptions import (
    GitHubAnonymousRateLimitError,
    MarketplaceError,
)
from homeassistant.components.marketplace.repositories import REPOSITORY_CLASSES
from homeassistant.components.marketplace.repositories.base import (
    FileInformation,
    Repository,
    RepositoryData,
    RepositoryManifest,
)
from homeassistant.components.marketplace.repositories.integration import (
    IntegrationRepository,
)
from homeassistant.components.marketplace.repositories.plugin import PluginRepository
from homeassistant.components.marketplace.repositories.theme import ThemeRepository
from homeassistant.components.marketplace.utils.validate import Validate
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import IntegrationNotLoaded

from . import (
    CategoryTestData,
    assert_api_usage,
    category_test_data_parametrized,
    github_api_calls,
    mocked_response,
)
from .conftest import MarketplaceResponses
from .const import REPOSITORY_INTEGRATION, REPOSITORY_PLUGIN

from tests.common import MockConfigEntry, async_mock_service
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse
from tests.typing import WebSocketGenerator

RATE_LIMITED = {"message": "API rate limit exceeded for 127.0.0.1."}


def _tree(*paths: tuple[str, bool]) -> list[GitHubGitTreeEntryModel]:
    """Return a repository tree of (path, is_directory) pairs."""
    return [
        GitHubGitTreeEntryModel({"path": path, "type": "tree" if directory else "blob"})
        for path, directory in paths
    ]


def _assets(*names: str) -> list[GitHubReleaseAssetModel]:
    """Return release assets with a download count derived from their position."""
    return [
        GitHubReleaseAssetModel({"name": name, "download_count": (index + 1) * 100})
        for index, name in enumerate(names)
    ]


def _zip_bytes(files: dict[str, str]) -> bytes:
    """Return the bytes of a zip archive holding the given files."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _installed_files(config_dir: Path) -> list[str]:
    """Return every file below the configuration directory, sorted."""
    return sorted(
        path.relative_to(config_dir).as_posix()
        for path in config_dir.rglob("*")
        if path.is_file()
    )


def test_manifest_defaults() -> None:
    """Test the defaults of a hacs.json that only carries a name."""
    manifest = RepositoryManifest.from_dict({"name": "TEST"})

    assert manifest.manifest == {"name": "TEST"}
    assert manifest.name == "TEST"
    assert manifest.content_in_root is False
    assert manifest.zip_release is False
    assert manifest.filename is None
    assert manifest.homeassistant is None
    assert manifest.persistent_directory is None
    assert manifest.hacs is None
    assert manifest.hide_default_branch is False


def test_manifest_rejects_none() -> None:
    """Test that a missing hacs.json is not silently accepted."""
    with pytest.raises(MarketplaceError):
        RepositoryManifest.from_dict(None)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        pytest.param("homeassistant", True, id="homeassistant-bool"),
        pytest.param("homeassistant", "", id="homeassistant-empty"),
        pytest.param("homeassistant", "2024.x.y", id="homeassistant-not-a-version"),
        pytest.param("homeassistant", ["2024.1"], id="homeassistant-list"),
        pytest.param("filename", 123, id="filename-number"),
        pytest.param("persistent_directory", 5, id="persistent-directory-number"),
        pytest.param("zip_release", "yes", id="zip-release-string"),
        pytest.param("name", {"en": "TEST"}, id="name-object"),
    ],
)
def test_manifest_leaves_out_values_of_the_wrong_type(key: str, value: Any) -> None:
    """Test a hacs.json value of the wrong type is left out, the rest is kept."""
    manifest = RepositoryManifest.from_dict({"hacs": "1.0.0", key: value})

    assert manifest.manifest == {"hacs": "1.0.0"}
    assert getattr(manifest, key) == getattr(RepositoryManifest(), key)


def test_repository_data_guards_generated_fields() -> None:
    """Test that the name derived from the full name can not be overwritten."""
    data = RepositoryData.create_from_dict({"full_name": "test/test"})
    assert data.name == "test"

    data.update_data({"name": "new"})
    assert data.name == "test"

    exported = data.to_json()
    exported["name"] = "new"
    assert data.name == "test"


def test_validate_collects_errors() -> None:
    """Test that a validation only succeeds while it has no errors."""
    validate = Validate()
    assert validate.success

    validate.errors.append("test")
    assert not validate.success


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"removal_type": "remove"}, id="removal-type"),
        pytest.param(
            {"reason": "Repository was removed from the Marketplace"}, id="reason"
        ),
        pytest.param({"link": "https://example.com/removed/repository"}, id="link"),
        pytest.param({"acknowledged": True}, id="acknowledged"),
        pytest.param({"acknowledged": False}, id="not-acknowledged"),
    ],
)
def test_removed_repository(data: dict[str, Any]) -> None:
    """Test updating the data of a removed repository."""
    base = {
        "repository": "removed/repository",
        "reason": None,
        "link": None,
        "removal_type": None,
        "acknowledged": False,
    }
    removed = RemovedRepository(repository="removed/repository")
    assert removed.to_json() == base

    removed.update_data(data)
    assert removed.to_json() == base | data


@pytest.mark.parametrize(
    ("ha_version", "required_version", "expected"),
    [
        pytest.param("1.0.0", "1.0.0b1", True, id="newer-than-beta"),
        pytest.param("1.0.0b1", "1.0.0", False, id="beta-of-required"),
        pytest.param("1.0.0b1", "1.0.0b2", False, id="older-beta"),
        pytest.param("1.0.0", "1.0.0", True, id="exact"),
    ],
)
async def test_can_install(
    marketplace: MarketplaceManager,
    ha_version: str,
    required_version: str,
    expected: bool,
) -> None:
    """Test whether a repository can be installed on this Home Assistant."""
    repository = Repository(marketplace)
    repository.data.releases = True
    repository.repository_manifest.homeassistant = required_version
    marketplace.version = AwesomeVersion(ha_version)

    assert repository.can_install is expected


async def test_can_install_without_requirement(
    marketplace: MarketplaceManager,
) -> None:
    """Test that a repository without a requirement can always be installed."""
    assert Repository(marketplace).can_install


async def test_display_status(marketplace: MarketplaceManager) -> None:
    """Test the status the frontend shows for a repository."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    assert repository.display_status == "default"

    repository.data.new = True
    assert repository.display_status == "new"
    repository.data.new = False

    repository.pending_restart = True
    assert repository.display_status == "pending-restart"
    repository.pending_restart = False

    repository.data.installed = True
    repository.data.installed_version = "1"
    repository.data.last_version = "2"
    repository.data.releases = True
    assert repository.display_status == "pending-upgrade"

    # A repository that needs a newer core still shows the pending upgrade
    marketplace.version = AwesomeVersion("0.0.0")
    repository.repository_manifest.homeassistant = "1.0.0"
    assert repository.display_status == "pending-upgrade"

    repository.data.last_version = "1"
    assert repository.display_status == "installed"


async def test_pending_update(marketplace: MarketplaceManager) -> None:
    """Test when a repository counts as having an update pending."""
    repository = Repository(marketplace)
    marketplace.version = AwesomeVersion("0.109.0")
    repository.repository_manifest.homeassistant = "0.110.0"
    repository.data.releases = True
    assert not repository.pending_update

    repository = Repository(marketplace)
    repository.data.installed = True
    repository.data.default_branch = "main"
    repository.data.selected_tag = "main"
    assert not repository.pending_update

    repository.data.installed_commit = "1"
    repository.data.last_commit = "2"
    assert repository.pending_update


@pytest.mark.parametrize(
    ("ref", "category", "releases", "zip_release", "expected"),
    [
        pytest.param(
            "dummy", RepositoryCategory.PLUGIN, True, False, True, id="plugin-release"
        ),
        pytest.param(
            "main", RepositoryCategory.PLUGIN, True, False, False, id="default-branch"
        ),
        pytest.param(
            "dummy",
            RepositoryCategory.INTEGRATION,
            True,
            False,
            False,
            id="wrong-category",
        ),
        pytest.param(
            "dummy", RepositoryCategory.THEME, True, False, False, id="theme-release"
        ),
        pytest.param(
            "dummy", RepositoryCategory.PLUGIN, False, False, False, id="no-releases"
        ),
        pytest.param(
            "dummy", RepositoryCategory.PLUGIN, False, True, True, id="zip-release"
        ),
        pytest.param(
            "main",
            RepositoryCategory.PLUGIN,
            False,
            True,
            False,
            id="zip-release-branch",
        ),
    ],
)
async def test_should_try_releases(
    marketplace: MarketplaceManager,
    ref: str,
    category: RepositoryCategory,
    releases: bool,
    zip_release: bool,
    expected: bool,
) -> None:
    """Test when the Marketplace looks at releases instead of the repository tree."""
    repository = REPOSITORY_CLASSES[category](marketplace, "test/test")
    repository.ref = ref
    repository.data.default_branch = "main"
    repository.data.releases = releases
    repository.repository_manifest.zip_release = zip_release
    repository.repository_manifest.filename = "test.zip" if zip_release else None

    assert repository.should_try_releases is expected


def test_gather_files_to_download(mock_repository: Repository) -> None:
    """Test gathering the files of a plain repository."""
    mock_repository.content.path.remote = ""
    mock_repository.tree = _tree(("test/path/file.file", False))

    assert [file.path for file in mock_repository.gather_files_to_download()] == [
        "test/path/file.file"
    ]


def test_gather_files_single_file_repository(mock_repository: Repository) -> None:
    """Test that a single file repository only downloads its one file."""
    mock_repository.content.single = True
    mock_repository.data.file_name = "test.file"
    mock_repository.tree = _tree(
        ("test.file", False),
        ("dir", True),
        ("test.yaml", False),
        ("readme.md", False),
    )

    assert [file.path for file in mock_repository.gather_files_to_download()] == [
        "test.file"
    ]


def test_gather_plugin_files_from_root(
    mock_repository_plugin: Repository,
) -> None:
    """Test that a plugin in the repository root only takes the root scripts."""
    mock_repository_plugin.content.path.remote = ""
    mock_repository_plugin.tree = _tree(
        ("test.js", False),
        ("dir", True),
        ("aaaa.js", False),
        ("dist/test.js", False),
    )
    mock_repository_plugin.update_filenames()

    files = [file.path for file in mock_repository_plugin.gather_files_to_download()]

    assert files == ["test.js", "aaaa.js"]


def test_gather_plugin_files_from_dist(
    mock_repository_plugin: Repository,
) -> None:
    """Test that a plugin in dist takes everything below dist."""
    mock_repository_plugin.content.path.remote = "dist"
    mock_repository_plugin.data.file_name = "test.js"
    mock_repository_plugin.tree = _tree(
        ("test.js", False),
        ("dist/image.png", False),
        ("dist/test.js", False),
        ("dist/subdir", True),
        ("dist/subdir/file.file", False),
    )

    files = [file.path for file in mock_repository_plugin.gather_files_to_download()]

    assert files == ["dist/image.png", "dist/test.js", "dist/subdir/file.file"]


def test_gather_plugin_files_multiple_in_root(
    mock_repository_plugin: Repository,
) -> None:
    """Test that the dependencies next to a plugin are downloaded too."""
    mock_repository_plugin.content.path.remote = ""
    mock_repository_plugin.data.file_name = "test.js"
    mock_repository_plugin.tree = _tree(
        ("test.js", False),
        ("dep1.js", False),
        ("dep2.js", False),
        ("info.md", False),
    )

    files = [file.path for file in mock_repository_plugin.gather_files_to_download()]

    assert files == ["test.js", "dep1.js", "dep2.js"]


def test_gather_plugin_files_from_release(
    mock_repository_plugin: Repository,
) -> None:
    """Test that a plugin release serves its assets instead of the tree."""
    mock_repository_plugin.data.file_name = "test.js"
    mock_repository_plugin.data.releases = True
    mock_repository_plugin.releases.objects = [
        GitHubReleaseModel(
            {
                "tag_name": "3",
                "assets": [{"name": "test.js"}, {"name": "test.png"}],
            }
        )
    ]

    files = [file.name for file in mock_repository_plugin.gather_files_to_download()]

    assert files == ["test.js", "test.png"]


def test_gather_zip_release(mock_repository_plugin: Repository) -> None:
    """Test that a zip release only serves the archive."""
    mock_repository_plugin.data.file_name = "test.zip"
    mock_repository_plugin.repository_manifest.zip_release = True
    mock_repository_plugin.repository_manifest.filename = "test.zip"
    mock_repository_plugin.releases.objects = [
        GitHubReleaseModel({"tag_name": "3", "assets": [{"name": "test.zip"}]})
    ]

    files = [file.name for file in mock_repository_plugin.gather_files_to_download()]

    assert files == ["test.zip"]


@pytest.mark.parametrize(
    "tree",
    [
        pytest.param(
            (("test.yaml", False), ("dir", True), ("test2.yaml", False)),
            id="other_yaml_in_the_root",
        ),
        pytest.param(
            (
                (".github/workflows/ci.yaml", False),
                ("README.md", False),
                ("test.yaml", False),
            ),
            id="yaml_in_a_hidden_folder_first",
        ),
    ],
)
def test_gather_theme_files_in_root(
    mock_repository_theme: Repository, tree: tuple[tuple[str, bool], ...]
) -> None:
    """Test that a theme in the repository root only takes its own yaml file."""
    mock_repository_theme.repository_manifest.content_in_root = True
    mock_repository_theme.content.path.remote = ""
    mock_repository_theme.data.file_name = "test.yaml"
    mock_repository_theme.tree = _tree(*tree)

    files = [file.path for file in mock_repository_theme.gather_files_to_download()]

    assert files == ["test.yaml"]


@pytest.mark.parametrize(
    ("file_name", "manifest_filename", "asset_names", "expected"),
    [
        pytest.param(
            "specific-file.js",
            None,
            ("wrong-file.js", "specific-file.js", "another-file.js"),
            "specific-file.js",
            id="configured-filename",
        ),
        pytest.param(
            None,
            "manifest-specified.js",
            ("wrong-file.js", "manifest-specified.js", "another-file.js"),
            "manifest-specified.js",
            id="manifest-filename",
        ),
        pytest.param(
            None,
            None,
            ("first-file.zip", "second-file.zip"),
            "first-file.zip",
            id="fallback-to-first",
        ),
        pytest.param(
            "mbapi2020.zip",
            None,
            ("Source code (zip)", "mbapi2020.zip"),
            "mbapi2020.zip",
            id="not-the-source-archive",
        ),
    ],
)
def test_find_target_asset(
    mock_repository: Repository,
    file_name: str | None,
    manifest_filename: str | None,
    asset_names: tuple[str, ...],
    expected: str,
) -> None:
    """Test which release asset the download count is read from."""
    mock_repository.data.file_name = file_name
    mock_repository.repository_manifest.filename = manifest_filename

    asset = mock_repository._find_target_asset(_assets(*asset_names))

    assert asset is not None
    assert asset.name == expected


@pytest.mark.parametrize(
    ("asset_names", "expected"),
    [
        pytest.param(("README.md", "test-card.js"), "test-card.js", id="plain"),
        pytest.param(
            ("README.md", "test-card-bundle.js"), "test-card-bundle.js", id="bundle"
        ),
        pytest.param(("README.md", "test-card.umd.js"), "test-card.umd.js", id="umd"),
    ],
)
def test_find_target_asset_plugin_patterns(
    mock_repository_plugin: Repository,
    asset_names: tuple[str, ...],
    expected: str,
) -> None:
    """Test that a plugin recognises its own script by name."""
    mock_repository_plugin.data.full_name = "user/test-card"
    mock_repository_plugin.data.file_name = None

    asset = mock_repository_plugin._find_target_asset(_assets(*asset_names))

    assert asset is not None
    assert asset.name == expected


def test_find_target_asset_prefers_configured_filename(
    mock_repository_plugin: Repository,
) -> None:
    """Test that the configured filename wins over the plugin name patterns."""
    mock_repository_plugin.data.full_name = "user/test-card"
    mock_repository_plugin.data.file_name = "specific-file.js"

    asset = mock_repository_plugin._find_target_asset(
        _assets("test-card.js", "specific-file.js", "test-card-bundle.js")
    )

    assert asset is not None
    assert asset.name == "specific-file.js"


@pytest.mark.parametrize(
    "assets",
    [pytest.param([], id="empty"), pytest.param(None, id="none")],
)
def test_find_target_asset_without_assets(
    mock_repository: Repository, assets: list[GitHubReleaseAssetModel] | None
) -> None:
    """Test a release that carries no assets at all."""
    assert mock_repository._find_target_asset(assets) is None


async def test_download_count_from_release(marketplace: MarketplaceManager) -> None:
    """Test that the download count comes from the matching release asset."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.file_name = "main.zip"
    repository.data.releases = True
    repository.releases.objects = [
        GitHubReleaseModel(
            {
                "tag_name": "1.0.0",
                "assets": [
                    {"name": "source-code.zip", "download_count": 5000},
                    {"name": "main.zip", "download_count": 2000},
                ],
            }
        )
    ]

    repository.ref = "1.0.0"

    repository._update_download_count()

    assert repository.data.downloads == 2000


async def test_removed_selected_version_falls_back(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a selected version GitHub no longer has falls back to the newest."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.selected_tag = "0.0.1"
    url = f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}/git/trees/0.0.1?recursive=true"
    response_mocker.add(
        url,
        mocked_response(
            url, status=HTTPStatus.NOT_FOUND, json_content={"message": "Not Found"}
        ),
    )

    await repository.common_update_data(force=True)

    assert repository.data.selected_tag is None
    assert repository.ref == "1.0.0"
    assert repository.tree_ref == "1.0.0"
    assert "Version 0.0.1 is no longer on GitHub, falling back to 1.0.0" in caplog.text


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        pytest.param("1.0.0", "Integration basic 1.0.0", id="known-version"),
        pytest.param("99.99.99", None, id="unknown-version"),
    ],
)
async def test_get_repository_manifest(
    marketplace: MarketplaceManager, version: str, expected: str | None
) -> None:
    """Test reading the hacs.json of a specific version."""
    repository = Repository(marketplace)
    repository.data.full_name = REPOSITORY_INTEGRATION

    manifest = await repository.get_repository_manifest(version=version)

    assert (manifest.name if manifest else None) == expected


async def test_get_repository_manifest_swallows_exceptions(
    marketplace: MarketplaceManager,
) -> None:
    """Test that a broken hacs.json never propagates out."""
    repository = Repository(marketplace)
    repository.data.full_name = REPOSITORY_INTEGRATION

    with patch.object(
        repository,
        "get_repository_manifest_raw",
        side_effect=Exception("Test exception"),
    ):
        assert await repository.get_repository_manifest(version="1.0.0") is None

    with patch(
        "homeassistant.components.marketplace.repositories.base.RepositoryManifest.from_dict",
        side_effect=ValueError("Invalid manifest"),
    ):
        assert await repository.get_repository_manifest(version="1.0.0") is None


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        pytest.param("1.0.0", {"name": "Integration basic 1.0.0"}, id="known-version"),
        pytest.param("99.99.99", None, id="unknown-version"),
    ],
)
async def test_get_repository_manifest_raw(
    marketplace: MarketplaceManager, version: str, expected: dict[str, Any] | None
) -> None:
    """Test reading the raw hacs.json of a specific version."""
    repository = Repository(marketplace)
    repository.data.full_name = REPOSITORY_INTEGRATION

    assert await repository.get_repository_manifest_raw(version=version) == expected


async def test_get_repository_manifest_raw_swallows_exceptions(
    marketplace: MarketplaceManager,
) -> None:
    """Test that an unreadable hacs.json never propagates out."""
    repository = Repository(marketplace)
    repository.data.full_name = REPOSITORY_INTEGRATION

    with patch.object(
        marketplace, "async_download_file", side_effect=Exception("boom")
    ):
        assert await repository.get_repository_manifest_raw(version="1.0.0") is None

    with patch(
        "homeassistant.components.marketplace.repositories.base.json_loads_object",
        side_effect=ValueError("Invalid JSON"),
    ):
        assert await repository.get_repository_manifest_raw(version="1.0.0") is None


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(
            {"installed": True, "installed_version": "1.0.0"},
            id="installed",
        ),
        pytest.param(
            {"installed": True, "installed_version": "1.0.0", "last_version": "2.0.0"},
            id="installed-with-update",
        ),
        pytest.param({"installed": False, "last_version": "2.0.0"}, id="available"),
        pytest.param(
            {"installed": False, "last_version": "99.99.99"}, id="unknown-version"
        ),
    ],
)
async def test_get_documentation(
    marketplace: MarketplaceManager, data: dict[str, Any], snapshot: SnapshotAssertion
) -> None:
    """Test which version of the documentation is served."""
    repository = Repository(marketplace)
    repository.data.full_name = REPOSITORY_INTEGRATION
    for key, value in data.items():
        setattr(repository.data, key, value)

    assert await repository.get_documentation(filename="README.md") == snapshot


@pytest.mark.parametrize(
    ("treefiles", "expected_filename"),
    [
        pytest.param(["info.md", "README.md"], "README.md", id="readme"),
        pytest.param(["info.md", "readme"], "readme", id="readme_without_extension"),
    ],
)
async def test_repository_page_uses_the_readme(
    marketplace: MarketplaceManager,
    treefiles: list[str],
    expected_filename: str,
) -> None:
    """Test the repository page shows the README, even when there is an info.md."""
    repository = Repository(marketplace)
    repository.data.full_name = REPOSITORY_INTEGRATION
    repository.treefiles = treefiles
    repository.repository_manifest = RepositoryManifest.from_dict(
        {"name": "TEST", "render_readme": False}
    )

    with patch.object(
        repository, "get_documentation", return_value="The README"
    ) as get_documentation:
        assert await repository.async_get_readme_contents() == "The README"

    get_documentation.assert_called_once_with(filename=expected_filename, version=None)


async def test_repository_page_ignores_info_file(
    marketplace: MarketplaceManager,
) -> None:
    """Test a repository with only an info.md has nothing to show."""
    repository = Repository(marketplace)
    repository.data.full_name = REPOSITORY_INTEGRATION
    repository.treefiles = ["info.md"]

    with patch.object(repository, "get_documentation") as get_documentation:
        assert await repository.async_get_readme_contents() == ""

    assert not get_documentation.called


async def test_get_documentation_without_filename(
    marketplace: MarketplaceManager,
) -> None:
    """Test that no filename means no documentation."""
    repository = Repository(marketplace)
    repository.data.full_name = REPOSITORY_INTEGRATION

    assert await repository.get_documentation() is None


async def test_get_documentation_without_version(
    marketplace: MarketplaceManager,
) -> None:
    """Test that a repository with nothing to point at has no documentation."""
    repository = Repository(marketplace)
    repository.data.full_name = REPOSITORY_INTEGRATION
    repository.ref = None

    assert await repository.get_documentation(filename="README.md") is None


@pytest.mark.parametrize(
    ("repository_full_name", "category"),
    [
        pytest.param(
            "hacs-test-org/integration-basic-custom",
            RepositoryCategory.INTEGRATION,
            id="integration",
        ),
        pytest.param(
            "hacs-test-org/plugin-custom-dist", RepositoryCategory.PLUGIN, id="plugin"
        ),
    ],
)
async def test_register_repository(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    repository_full_name: str,
    category: RepositoryCategory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test adding a repository the Marketplace did not know about."""
    assert marketplace.repositories.get_by_full_name(repository_full_name) is None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repositories/add",
            "repository": repository_full_name,
            "category": category.value,
        }
    )
    assert (await client.receive_json())["success"]

    repository = marketplace.repositories.get_by_full_name(repository_full_name)
    assert repository is not None

    await client.send_json_auto_id(
        {"type": "marketplace/repository/info", "repository_id": repository.data.id}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == snapshot(exclude=props("local_path"))


APP_REPOSITORY_MESSAGE = (
    "{repository} holds apps, the Marketplace does not install apps"
)


@pytest.mark.parametrize(
    ("repository_full_name", "translation_key", "message", "placeholders"),
    [
        pytest.param(
            "home-assistant/core",
            "core_repository",
            "The integrations of Home Assistant itself come with Home Assistant,"
            " there is nothing to add",
            None,
            id="core",
        ),
        pytest.param(
            "home-assistant/addons",
            "app_repository",
            APP_REPOSITORY_MESSAGE.format(repository="home-assistant/addons"),
            {"repository": "home-assistant/addons"},
            id="core-addons",
        ),
        pytest.param(
            "hassio-addons/example",
            "app_repository",
            APP_REPOSITORY_MESSAGE.format(repository="hassio-addons/example"),
            {"repository": "hassio-addons/example"},
            id="addon-org",
        ),
        pytest.param(
            "hacs-test-org/addon-basic",
            "app_repository",
            APP_REPOSITORY_MESSAGE.format(repository="hacs-test-org/addon-basic"),
            {"repository": "hacs-test-org/addon-basic"},
            id="addon-repository",
        ),
        pytest.param(
            "hacs-test-org/integration-invalid",
            "add_failed",
            "Adding hacs-test-org/integration-invalid failed:"
            " <Integration hacs-test-org/integration-invalid> Repository structure"
            " for main is not compliant",
            {
                "repository": "hacs-test-org/integration-invalid",
                "error": "<Integration hacs-test-org/integration-invalid>"
                " Repository structure for main is not compliant",
            },
            id="not-compliant",
        ),
    ],
)
async def test_register_repository_failures(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    repository_full_name: str,
    translation_key: str,
    message: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test a repository that can not be added is answered with the reason."""
    assert marketplace.repositories.get_by_full_name(repository_full_name) is None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repositories/add",
            "repository": repository_full_name,
            "category": RepositoryCategory.INTEGRATION.value,
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": translation_key,
        "message": message,
        "translation_key": translation_key,
        "translation_domain": DOMAIN,
        "translation_placeholders": placeholders,
    }
    assert marketplace.repositories.get_by_full_name(repository_full_name) is None


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_validate_repository(
    marketplace: MarketplaceManager, category_test_data: CategoryTestData
) -> None:
    """Test validating the structure of a repository of every category."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    await repository.update_repository(force=True)

    assert await repository.validate_repository()
    assert repository.validate.errors == []


@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(
        categories=[RepositoryCategory.TEMPLATE, RepositoryCategory.THEME]
    ),
)
async def test_validate_repository_without_content(
    marketplace: MarketplaceManager, category_test_data: CategoryTestData
) -> None:
    """Test that a repository without the expected content is refused."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    await repository.update_repository(force=True)

    repository.tree = _tree(("README.md", False))
    repository.treefiles = ["README.md"]

    with (
        patch.object(repository, "common_validate"),
        pytest.raises(MarketplaceError, match="is not compliant"),
    ):
        await repository.validate_repository()


@pytest.mark.parametrize(
    "installed_commit",
    [
        pytest.param("1234567", id="digits"),
        pytest.param("3730b11", id="digits_and_b"),
        pytest.param("7fd1a60", id="letters"),
    ],
)
async def test_first_release_after_a_commit(
    marketplace: MarketplaceManager, installed_commit: str
) -> None:
    """Test a repository installed as a commit sees its first release."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.installed = True
    repository.data.installed_version = None
    repository.data.installed_commit = installed_commit
    repository.data.releases = True
    repository.data.last_version = "0.2.0"

    assert repository.pending_update


async def test_validate_repository_without_manifest(
    marketplace: MarketplaceManager,
) -> None:
    """Test a repository without hacs.json is refused, it could not be updated."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.tree = _tree(("custom_components/example/manifest.json", False))

    with patch.object(repository, "common_update_data"):
        await repository.common_validate()

    assert repository.validate.errors == [
        f"{REPOSITORY_INTEGRATION} has no hacs.json in its root, the Marketplace "
        "needs one to install it"
    ]


async def test_validate_integration_without_content(
    marketplace: MarketplaceManager,
) -> None:
    """Test an integration repository without a custom_components directory."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    await repository.update_repository(force=True)

    repository.tree = _tree(("README.md", False))
    repository.treefiles = ["README.md"]
    repository.content.path.remote = "custom_components"

    with (
        patch.object(repository, "common_validate"),
        pytest.raises(MarketplaceError, match="is not compliant"),
    ):
        await repository.validate_repository()


async def test_validate_plugin_without_content(marketplace: MarketplaceManager) -> None:
    """Test a dashboard plugin repository without a script to serve."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    await repository.update_repository(force=True)

    repository.tree = _tree(("README.md", False))
    repository.treefiles = ["README.md"]
    repository.content.path.remote = None

    with (
        patch.object(repository, "common_validate"),
        pytest.raises(MarketplaceError, match="is not compliant"),
    ):
        await repository.validate_repository()


@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(categories=[RepositoryCategory.THEME]),
)
async def test_validate_repository_with_content_in_root(
    marketplace: MarketplaceManager, category_test_data: CategoryTestData
) -> None:
    """Test a repository that keeps its content in the repository root."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    await repository.update_repository(force=True)
    repository.repository_manifest.content_in_root = True
    # With the content in the root, the theme is there too
    repository.treefiles = ["hacs.json", "example.yaml", "README.md"]

    # The common validation refetches the manifest, which would undo the change
    with patch.object(repository, "common_validate"):
        assert await repository.validate_repository()

    assert repository.content.path.remote == ""


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_update_repository_without_a_tree(
    marketplace: MarketplaceManager, category_test_data: CategoryTestData
) -> None:
    """Test that a refresh that finds no files keeps the known tree."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    await repository.update_repository(force=True)

    with patch.object(repository, "get_tree", return_value=[]):
        await repository.update_repository(ignore_issues=True, force=True)

    assert repository.tree


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_install_repository(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    config_dir: Path,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test installing a repository of every category."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    assert repository is not None
    assert repository.data.installed is False
    assert marketplace.repositories.list_installed == []

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/install", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]

    assert repository.data.installed is True
    assert repository.data.installed_version == category_test_data["version_base"]
    assert marketplace.repositories.list_installed == [repository]
    assert _installed_files(config_dir) == snapshot


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_update_repository(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    category_test_data: CategoryTestData,
) -> None:
    """Test installing a specific newer version of a repository."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    assert repository is not None

    repository.data.installed = True
    repository.data.installed_version = category_test_data["version_base"]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "marketplace/repository/install",
            "repository": repository.data.id,
            "version": category_test_data["version_update"],
        }
    )
    assert (await client.receive_json())["success"]

    assert repository.data.installed_version == category_test_data["version_update"]


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_uninstall_repository(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    config_dir: Path,
    category_test_data: CategoryTestData,
) -> None:
    """Test uninstalling a repository of every category."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    assert repository is not None

    repository.data.installed = True
    repository.data.file_name = category_test_data["files"][0]
    repository.content.path.local = repository.localpath

    for name in category_test_data["files"]:
        file = Path(repository.localpath, name)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()

    assert _installed_files(config_dir)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/uninstall", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]

    assert repository.data.installed is False
    assert marketplace.repositories.list_installed == []
    assert _installed_files(config_dir) == []


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(
        categories=[RepositoryCategory.TEMPLATE, RepositoryCategory.THEME]
    ),
)
async def test_uninstall_repository_after_a_restart(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_dir: Path,
    category_test_data: CategoryTestData,
) -> None:
    """Test a single file repository can still be removed after a restart."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    assert (await _install(hass, hass_ws_client, repository.data.id))["success"]
    assert _installed_files(config_dir)

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    aioclient_mock.mock_calls.clear()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/uninstall", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]

    assert _installed_files(config_dir) == []
    # The stored file name is enough, GitHub is not asked
    assert not github_api_calls(aioclient_mock)


@pytest.mark.parametrize("github_token", [None])
async def test_uninstall_theme_stored_without_its_file_name(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    mock_config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    config_dir: Path,
) -> None:
    """Test a theme taken over from HACS learns its file name before uninstalling."""
    repository = marketplace.repositories.get_by_full_name("hacs-test-org/theme-basic")
    assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    # What HACS stored does not know the file name
    repository.data.file_name = ""
    await marketplace.data.async_write()
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/uninstall", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]
    assert _installed_files(config_dir) == []


async def test_uninstall_repository_failure_is_answered(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an uninstall that can not go ahead answers with why."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.installed = True

    client = await hass_ws_client(hass)
    with patch.object(repository, "remove_local_directory", return_value=False):
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/uninstall",
                "repository": repository.data.id,
            }
        )
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"] == {
        "code": "uninstall_failed",
        "message": f"Could not uninstall {REPOSITORY_INTEGRATION}, see the log for details",
        "translation_key": "uninstall_failed",
        "translation_domain": DOMAIN,
        "translation_placeholders": {"repository": REPOSITORY_INTEGRATION},
    }
    assert repository.data.installed


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_repository_releases(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test listing the releases of a repository."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    assert repository is not None

    response_mocker.add(
        f"https://api.github.com/repos/{category_test_data['repository']}/releases",
        mocked_response(
            f"https://api.github.com/repos/{category_test_data['repository']}/releases",
            json_content=[
                {
                    "name": category_test_data["version_update"],
                    "tag_name": category_test_data["version_update"],
                    "published_at": "2019-02-26T15:02:39Z",
                    "prerelease": False,
                }
            ],
        ),
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/releases", "repository_id": repository.data.id}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == snapshot


async def test_releases_with_an_unusable_tag_are_left_out(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a release whose tag breaks the URLs it is installed by is not offered."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    url = f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}/releases"
    releases = [
        {
            "name": tag,
            "tag_name": tag,
            "published_at": "2019-02-26T15:02:39Z",
            "prerelease": False,
            "draft": False,
        }
        for tag in ("2.0.0#latest", "1.5%2F..", "1.0.0")
    ]
    response_mocker.add(url, mocked_response(url, json_content=releases), keep=True)

    assert [release.tag_name for release in await repository.get_releases()] == [
        "1.0.0"
    ]
    assert [release.tag_name for release in await repository.async_get_releases()] == [
        "1.0.0"
    ]


async def test_download_zip_release(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test downloading a release that ships a zip archive."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.ref = "1.0.0"
    repository.repository_manifest.zip_release = True
    repository.repository_manifest.filename = "release.zip"
    repository.content.path.local = repository.localpath

    url = f"https://github.com/{REPOSITORY_INTEGRATION}/releases/download/1.0.0/release.zip"
    response_mocker.add(
        url,
        mocked_response(
            url, content=_zip_bytes({"example/__init__.py": "", "example/const.py": ""})
        ),
    )

    validate = Validate()
    await repository.download_zip_files(validate)

    assert validate.success
    assert _installed_files(config_dir) == [
        "custom_components/example/example/__init__.py",
        "custom_components/example/example/const.py",
    ]


async def test_download_zip_release_failure(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a zip release that can not be downloaded."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.ref = "1.0.0"
    repository.repository_manifest.filename = "release.zip"
    repository.content.path.local = repository.localpath

    url = f"https://github.com/{REPOSITORY_INTEGRATION}/releases/download/1.0.0/release.zip"
    response_mocker.add(
        url, mocked_response(url, status=HTTPStatus.SERVICE_UNAVAILABLE), keep=True
    )

    validate = Validate()
    await repository.download_zip_files(validate)

    assert not validate.success
    assert validate.errors == [f"Failed to download {url}"]


async def test_download_repository_zip_without_ref(
    marketplace: MarketplaceManager,
) -> None:
    """Test that a repository archive needs something to download."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.ref = ""

    with pytest.raises(MarketplaceError, match="Missing required elements"):
        await repository.download_repository_zip()


async def test_download_zip_release_escaping_member(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test a zip release that tries to write outside the repository."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.ref = "1.0.0"
    repository.repository_manifest.zip_release = True
    repository.repository_manifest.filename = "release.zip"
    repository.content.path.local = repository.localpath

    url = f"https://github.com/{REPOSITORY_INTEGRATION}/releases/download/1.0.0/release.zip"
    response_mocker.add(
        url, mocked_response(url, content=_zip_bytes({"../../escaped.py": ""}))
    )

    validate = Validate()
    await repository.download_zip_files(validate)

    assert not validate.success
    assert _installed_files(config_dir) == []


async def test_download_zip_release_too_large(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test a zip release that expands to more than the limit."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.ref = "1.0.0"
    repository.repository_manifest.zip_release = True
    repository.repository_manifest.filename = "release.zip"
    repository.content.path.local = repository.localpath

    url = f"https://github.com/{REPOSITORY_INTEGRATION}/releases/download/1.0.0/release.zip"
    response_mocker.add(
        url,
        mocked_response(url, content=_zip_bytes({"example/__init__.py": "content"})),
    )

    validate = Validate()
    with patch(
        "homeassistant.components.marketplace.repositories.base.MAX_DOWNLOAD_SIZE", 1
    ):
        await repository.download_zip_files(validate)

    assert not validate.success
    assert _installed_files(config_dir) == []


async def test_download_repository_zip_escaping_member(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test a repository archive that tries to write outside the repository."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.ref = "1.0.0"
    repository.content.path.local = repository.localpath
    repository.content.path.remote = "custom_components"

    url = f"https://github.com/{REPOSITORY_INTEGRATION}/archive/refs/tags/1.0.0.zip"
    response_mocker.add(
        url,
        mocked_response(
            url,
            content=_zip_bytes(
                {"integration-basic-1.0.0/custom_components/../../escaped.py": ""}
            ),
        ),
    )

    with pytest.raises(MarketplaceError, match="is not inside"):
        await repository.download_repository_zip()

    assert _installed_files(config_dir) == []


async def test_download_content_outside_the_repository(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test a file name that tries to write outside the repository."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.content.path.local = repository.localpath
    repository.content.single = True

    url = f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/1.0.0/escaped.py"
    response_mocker.add(url, mocked_response(url, content=b""))

    await repository.download_repository_file(
        FileInformation(url, "escaped.py", "../../escaped.py")
    )

    assert "is not inside" in repository.validate.errors[0]
    assert _installed_files(config_dir) == []


async def test_install_rejects_escaping_persistent_directory(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test a hacs.json pointing its persistent directory out of the repository."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.content.path.local = repository.localpath
    repository.repository_manifest.persistent_directory = "../.."

    with (
        patch.object(repository, "update_repository"),
        pytest.raises(MarketplaceError, match="is not inside"),
    ):
        await repository._async_write_version()

    assert _installed_files(config_dir) == []


@pytest.mark.parametrize(
    ("github_token", "disabled_reason", "reauth_flows"),
    [
        pytest.param("token", DisabledReason.INVALID_TOKEN, 1, id="connected"),
        pytest.param(None, None, 0, id="anonymous"),
    ],
)
async def test_repository_object_with_a_bad_token(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    disabled_reason: DisabledReason | None,
    reauth_flows: int,
) -> None:
    """Test a token that stopped working asks to connect GitHub again."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    with (
        patch.object(
            marketplace.githubapi.repos,
            "get",
            side_effect=GitHubAuthenticationException("Bad credentials"),
        ),
        pytest.raises(MarketplaceError),
    ):
        await repository.async_get_repository_object()
    await hass.async_block_till_done()

    assert marketplace.system.disabled_reason == disabled_reason
    assert (
        len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == reauth_flows
    )


@pytest.mark.parametrize(
    ("download_error", "raised"),
    [
        pytest.param(
            MarketplaceError("No content to download"), MarketplaceError, id="error"
        ),
        pytest.param(
            GitHubAnonymousRateLimitError("API rate limit exceeded"),
            GitHubAnonymousRateLimitError,
            id="rate_limit",
        ),
        pytest.param(
            OSError(28, "No space left on device"), MarketplaceError, id="disk_full"
        ),
    ],
)
async def test_install_failure_restores_the_installed_files(
    marketplace: MarketplaceManager,
    download_error: Exception,
    raised: type[Exception],
) -> None:
    """Test a failed install puts the repository and its user files back."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.installed = True
    repository.content.path.local = repository.localpath
    repository.repository_manifest.persistent_directory = "userfiles"

    local_path = Path(repository.content.path.local)
    (local_path / "userfiles").mkdir(parents=True)
    (local_path / "__init__.py").write_text("installed")
    (local_path / "userfiles" / "settings.yaml").write_text("mine")

    with (
        patch.object(repository, "update_repository"),
        patch.object(repository, "download_content", side_effect=download_error),
        pytest.raises(raised),
    ):
        await repository._async_write_version(version="2.0.0")

    assert (local_path / "__init__.py").read_text() == "installed"
    assert (local_path / "userfiles" / "settings.yaml").read_text() == "mine"


async def test_download_keeps_tags_in_the_url(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a repository or folder named with tags is downloaded from its URL."""
    url = "https://raw.githubusercontent.com/owner/hashtags/1.0.0/tags/card.js"
    response_mocker.add(url, mocked_response(url, content=b"card"))

    assert await marketplace.async_download_file(url) == b"card"


async def test_download_declines_a_declared_size_over_the_limit(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test that a response declaring more than the limit is not read."""
    url = "https://example.com/big"
    response_mocker.add(
        url,
        mocked_response(
            url, content=b"", headers={"Content-Length": str(MAX_DOWNLOAD_SIZE + 1)}
        ),
    )

    assert await marketplace.async_download_file(url) is None


async def test_download_discards_content_over_the_limit(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test that a response larger than the limit is thrown away."""
    url = "https://example.com/big"
    response_mocker.add(url, mocked_response(url, content=b"0123456789"))

    with patch(
        "homeassistant.components.marketplace.utils.response.MAX_DOWNLOAD_SIZE", 5
    ):
        assert await marketplace.async_download_file(url) is None


class _EndlessStream:
    """A response body that never ends, counting the chunks handed out."""

    def __init__(self) -> None:
        """Initialize."""
        self.chunks_read = 0

    async def iter_chunked(self, size: int) -> AsyncIterator[bytes]:
        """Yield chunks forever."""
        while True:
            self.chunks_read += 1
            yield b"0" * size


class _EndlessResponse(AiohttpClientMockResponse):
    """A response without a Content-Length whose body never ends."""

    def __init__(self, url: str, stream: _EndlessStream) -> None:
        """Initialize."""
        super().__init__("get", URL(url))
        self._stream = stream

    @property
    def content(self) -> _EndlessStream:
        """Return the endless body."""
        return self._stream


async def test_download_stops_reading_at_the_limit(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a body without a Content-Length is not read past the limit."""
    url = "https://example.com/endless"
    stream = _EndlessStream()
    response_mocker.add(url, _EndlessResponse(url, stream))

    with (
        patch(
            "homeassistant.components.marketplace.utils.response.MAX_DOWNLOAD_SIZE",
            1000,
        ),
        patch(
            "homeassistant.components.marketplace.utils.response.DOWNLOAD_CHUNK_SIZE",
            100,
        ),
    ):
        assert await marketplace.async_download_file(url) is None

    # The chunk that passes the limit is the last one read
    assert stream.chunks_read == 11


@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(categories=[RepositoryCategory.TEMPLATE]),
)
async def test_remove_refuses_escaping_file_name(
    marketplace: MarketplaceManager,
    config_dir: Path,
    category_test_data: CategoryTestData,
) -> None:
    """Test that a crafted file name can not delete a file of its own choosing."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    repository.content.path.local = repository.localpath
    repository.data.file_name = "../configuration.yaml"

    target = config_dir / "configuration.yaml"
    target.touch()

    assert not await repository.remove_local_directory()
    assert target.exists()


async def test_remove_refuses_integration_domain_outside_custom_components(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test a stored domain can not point the removal outside custom_components."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.domain = ".."
    repository.content.path.local = repository.localpath

    target = config_dir / "configuration.yaml"
    target.touch()

    assert not await repository.remove_local_directory()
    assert target.exists()


async def test_remove_refuses_plugin_name_outside_community(
    marketplace: MarketplaceManager, config_dir: Path
) -> None:
    """Test a repository name can not point the removal at www itself."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    repository.data.full_name = "hacs-test-org/.."
    repository.content.path.local = repository.localpath

    target = config_dir / "www" / "keep.js"
    target.parent.mkdir(exist_ok=True)
    target.touch()

    assert not await repository.remove_local_directory()
    assert target.exists()


@pytest.mark.parametrize(
    ("config_flow", "loaded", "found", "restart"),
    [
        pytest.param(True, False, {"example"}, False, id="new"),
        pytest.param(True, True, {"example"}, True, id="known_to_the_loader"),
        pytest.param(False, False, {"example"}, True, id="set_up_from_yaml"),
        # The scan does not find it, like an integration the loader refuses
        pytest.param(True, False, set(), True, id="not_found_by_the_loader"),
    ],
)
async def test_integration_restart_required_issue(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    issue_registry: ir.IssueRegistry,
    hass_ws_client: WebSocketGenerator,
    config_flow: bool,
    loaded: bool,
    found: set[str],
    restart: bool,
) -> None:
    """Test an install only asks for a restart when this run can not load it."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    use_manifest = IntegrationRepository._use_integration_manifest

    def manifest(self: IntegrationRepository, content: dict[str, Any]) -> None:
        use_manifest(self, content | {"config_flow": config_flow})

    client = await hass_ws_client(hass)
    with (
        patch.object(IntegrationRepository, "_use_integration_manifest", manifest),
        patch(
            "homeassistant.components.marketplace.repositories.integration"
            ".async_get_loaded_integration",
            side_effect=None if loaded else IntegrationNotLoaded("example"),
        ),
        patch(
            "homeassistant.components.marketplace.repositories.integration"
            ".async_get_custom_components",
            return_value=dict.fromkeys(found),
        ),
    ):
        await client.send_json_auto_id(
            {
                "type": "marketplace/repository/install",
                "repository": repository.data.id,
            }
        )
        assert (await client.receive_json())["success"]

    assert repository.pending_restart is restart
    issue = issue_registry.async_get_issue(
        "marketplace", f"restart_required_{repository.data.id}_{repository.ref}"
    )
    assert (issue is not None) is restart


async def test_first_integration_is_found_without_a_restart(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    issue_registry: ir.IssueRegistry,
    hass_ws_client: WebSocketGenerator,
    config_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the first install creates custom_components and can be set up now."""
    # A fresh instance: nothing mounted custom_components, the folder is not there
    monkeypatch.delitem(sys.modules, "custom_components", raising=False)
    assert not (config_dir / "custom_components").exists()
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    use_manifest = IntegrationRepository._use_integration_manifest

    def manifest(self: IntegrationRepository, content: dict[str, Any]) -> None:
        use_manifest(self, content | {"config_flow": True})

    client = await hass_ws_client(hass)
    with patch.object(IntegrationRepository, "_use_integration_manifest", manifest):
        await client.send_json_auto_id(
            {"type": "marketplace/repository/install", "repository": repository.data.id}
        )
        assert (await client.receive_json())["success"]

    assert not repository.pending_restart
    assert not issue_registry.async_get_issue(
        "marketplace", f"restart_required_{repository.data.id}_{repository.ref}"
    )


async def test_integration_manifest_missing_key(
    marketplace: MarketplaceManager,
) -> None:
    """Test an integration manifest without a domain."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    with patch.object(
        repository, "async_get_integration_manifest", return_value={"name": "Example"}
    ):
        assert not await repository.validate_repository()

    assert repository.validate.errors == [
        "Missing expected key ''domain'' in manifest.json"
    ]


@pytest.mark.parametrize(
    "domain",
    [
        pytest.param("../../evil", id="traversal"),
        pytest.param("with/slash", id="slash"),
        pytest.param("Example", id="uppercase"),
        pytest.param("", id="empty"),
        pytest.param(1337, id="not_a_string"),
    ],
)
async def test_integration_manifest_invalid_domain(
    marketplace: MarketplaceManager, domain: Any
) -> None:
    """Test that a manifest can not name a directory of its own choosing."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    with (
        patch.object(
            repository,
            "async_get_integration_manifest",
            return_value={"domain": domain, "name": "Example"},
        ),
        pytest.raises(MarketplaceError, match="is not a valid integration domain"),
    ):
        await repository.validate_repository()


async def test_integration_manifest_hyphenated_domain(
    marketplace: MarketplaceManager,
) -> None:
    """Test a domain with a hyphen, which the catalog has a few of, is accepted."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    with patch.object(
        repository,
        "async_get_integration_manifest",
        return_value={"domain": "meteo-swiss", "name": "Example"},
    ):
        await repository.validate_repository()

    assert repository.data.domain == "meteo-swiss"


async def test_integration_manifest_domain_changed_after_install(
    marketplace: MarketplaceManager,
) -> None:
    """Test an installed integration keeps the directory its files are in."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.installed = True
    repository.data.domain = "example"

    with (
        patch.object(
            repository,
            "async_get_integration_manifest",
            return_value={"domain": "renamed", "name": "Example"},
        ),
        pytest.raises(MarketplaceError, match="changed its domain from 'example'"),
    ):
        await repository.validate_repository()

    assert repository.data.domain == "example"


async def test_integration_domain_owned_by_another_repository(
    marketplace: MarketplaceManager,
) -> None:
    """Test that an install can not take over the directory of another one."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.domain = "example"

    other = IntegrationRepository(marketplace, "test/other")
    other.data.id = "1337"
    other.data.domain = "example"
    other.data.installed = True
    marketplace.repositories.register(other)

    with pytest.raises(MarketplaceError, match="is owned by test/other"):
        await repository.async_pre_install()


async def test_plugin_directory_owned_by_another_repository(
    marketplace: MarketplaceManager,
) -> None:
    """Test a plugin of another owner can not take over the same directory."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    repository.content.path.remote = ""

    other = PluginRepository(marketplace, "someone-else/Plugin-Basic")
    other.data.id = "1337"
    other.data.installed = True
    marketplace.repositories.register(other)

    with pytest.raises(MarketplaceError, match="is owned by someone-else/Plugin-Basic"):
        await repository.async_pre_install()


@pytest.mark.parametrize(
    ("key", "value", "attribute", "default"),
    [
        pytest.param("codeowners", [42], "authors", [], id="codeowners_numbers"),
        pytest.param("codeowners", "@owner", "authors", [], id="codeowners_string"),
        pytest.param("name", 42, "manifest_name", None, id="name_number"),
        pytest.param(
            "config_flow", "no", "config_flow", False, id="config_flow_string"
        ),
    ],
)
def test_integration_manifest_values_of_the_wrong_type(
    marketplace: MarketplaceManager,
    key: str,
    value: Any,
    attribute: str,
    default: Any,
) -> None:
    """Test a manifest.json value of the wrong type is left out."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    repository._use_integration_manifest({"domain": "example", key: value})

    assert getattr(repository.data, attribute) == default


async def test_card_release_takes_the_file_name_of_its_own_assets(
    marketplace: MarketplaceManager,
) -> None:
    """Test an older release names its file itself, not after the newest one."""
    repository = PluginRepository(marketplace, "owner/card")
    # What the newest release named, before the older one is written
    repository.data.file_name = "card.js"
    release = MagicMock(
        data={
            "assets": [
                {
                    "name": "card-bundle.js",
                    "browser_download_url": "https://example.com/card-bundle.js",
                    "size": 10,
                }
            ]
        }
    )

    with patch.object(
        marketplace, "async_github_api_method", AsyncMock(return_value=release)
    ):
        await repository.release_contents("1.0.0")

    assert repository.data.file_name == "card-bundle.js"


async def test_integration_moving_out_of_the_root_is_found(
    marketplace: MarketplaceManager,
) -> None:
    """Test a version with its files in custom_components after one in the root."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    # What the previous version, with content_in_root, left behind
    repository.content.path.remote = ""
    repository.repository_manifest.content_in_root = False
    repository.tree = _tree(
        ("custom_components", True),
        ("custom_components/example", True),
        ("custom_components/example/manifest.json", False),
    )

    with (
        patch.object(repository, "common_update", AsyncMock(return_value=True)),
        patch.object(
            repository,
            "async_get_integration_manifest",
            AsyncMock(return_value={"domain": "example"}),
        ),
    ):
        await repository.update_repository(force=True)

    assert repository.content.path.remote == "custom_components/example"


async def test_integration_manifest_missing_file(
    marketplace: MarketplaceManager,
) -> None:
    """Test an integration that has no manifest.json in its tree."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.tree = []

    with pytest.raises(MarketplaceError, match="No manifest.json file found"):
        await repository.async_get_integration_manifest()


async def test_integration_manifest_for_version(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test reading the integration manifest of a specific version."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    await repository.update_repository(force=True)

    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/1.0.0"
        "/custom_components/example/manifest.json"
    )
    response_mocker.add(url, mocked_response(url, json_content={"domain": "example"}))

    assert await repository._async_download_integration_manifest(
        "1.0.0", "custom_components/example/manifest.json"
    ) == {"domain": "example"}


async def test_integration_manifest_for_missing_version(
    marketplace: MarketplaceManager,
) -> None:
    """Test the integration manifest of a version that was never published."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    await repository.update_repository(force=True)

    assert (
        await repository._async_download_integration_manifest(
            "99.99.99", "custom_components/example/manifest.json"
        )
        is None
    )


async def test_template_reloads_custom_templates(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that removing a template repository reloads the custom templates."""
    repository = marketplace.repositories.get_by_full_name(
        "hacs-test-org/template-basic"
    )
    repository.data.installed = True
    repository.data.file_name = "example.jinja"
    repository.content.path.local = repository.localpath

    file = Path(repository.localpath)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    reloads = async_mock_service(hass, "homeassistant", "reload_custom_templates")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/uninstall", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]

    assert len(reloads) == 1


@pytest.fixture
async def installed_plugin(marketplace: MarketplaceManager) -> PluginRepository:
    """Return an installed dashboard plugin repository."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    await repository.async_install()
    return repository


@pytest.mark.parametrize(
    ("directory", "namespace"),
    [
        pytest.param("plugin-basic", "/local/community/plugin-basic", id="installed"),
        pytest.param(None, "/local/community/plugin-advanced", id="no_folder_yet"),
    ],
)
async def test_dashboard_namespace(
    installed_plugin: PluginRepository, directory: str | None, namespace: str
) -> None:
    """Test a card serves its files from its folder, even after a rename."""
    installed_plugin.data.full_name = "hacs-test-org/plugin-advanced"
    installed_plugin.data.directory = directory

    assert installed_plugin.generate_dashboard_resource_namespace() == namespace


@pytest.mark.parametrize(
    ("installed", "selected", "available", "expected"),
    [
        pytest.param(None, None, None, "-", id="nothing-known"),
        pytest.param("1.0.0", None, None, "-1.0.0", id="installed"),
        pytest.param(None, "2.0.1", None, "-2.0.1", id="selected"),
        pytest.param(None, None, "3.4.2", "-3.4.2", id="available"),
        pytest.param("1.7-dev09-r2", None, None, "-1.7-dev09-r2", id="non-numeric"),
        pytest.param("v1.0+build/1", None, None, "-v1.0%2Bbuild%2F1", id="encoded"),
    ],
)
async def test_dashboard_resource_tag(
    installed_plugin: PluginRepository,
    installed: str | None,
    selected: str | None,
    available: str | None,
    expected: str,
) -> None:
    """Test the cache busting tag of a dashboard resource."""
    installed_plugin.data.installed_commit = None
    installed_plugin.data.last_commit = None
    installed_plugin.data.installed_version = installed
    installed_plugin.data.last_version = available
    installed_plugin.data.selected_tag = selected

    assert (
        installed_plugin.generate_dashboard_resource_tag()
        == f"{installed_plugin.data.id}{expected}"
    )


async def test_dashboard_url(installed_plugin: PluginRepository) -> None:
    """Test the URL a dashboard resource is registered with."""
    assert (
        installed_plugin.generate_dashboard_resource_url()
        == "/local/community/plugin-basic/plugin-basic.js?v=1296267-1.0.0"
    )


async def test_dashboard_url_with_invalid_file_name(
    installed_plugin: PluginRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a plugin pointing at a subdirectory is flattened and logged."""
    installed_plugin.data.file_name = "dist/plugin-basic.js"

    assert (
        installed_plugin.generate_dashboard_resource_url()
        == "/local/community/plugin-basic/plugin-basic.js?v=1296267-1.0.0"
    )
    assert "have defined an invalid file name dist/plugin-basic.js" in caplog.text


@pytest.mark.parametrize(
    ("created_www_directory", "expect_issue"),
    [
        pytest.param(True, True, id="www-created-this-session"),
        pytest.param(False, False, id="www-already-served"),
    ],
)
async def test_dashboard_resource_restart_issue(
    marketplace: MarketplaceManager,
    issue_registry: ir.IssueRegistry,
    created_www_directory: bool,
    expect_issue: bool,
) -> None:
    """Test that a resource in a www directory we created asks for a restart."""
    marketplace.status.created_www_directory = created_www_directory
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)

    await repository.async_install()

    issue = issue_registry.async_get_issue(
        "marketplace", f"restart_required_{repository.data.id}_{repository.ref}"
    )
    assert (issue is not None) is expect_issue


async def test_resource_handler(installed_plugin: PluginRepository) -> None:
    """Test that the dashboard resources are reachable in storage mode."""
    assert installed_plugin._get_resource_handler() is not None


@pytest.mark.parametrize(
    ("attribute", "value", "message"),
    [
        pytest.param(
            "version", 2, "Can not use the dashboard resources", id="wrong-version"
        ),
        pytest.param(
            "key",
            "wrong_key",
            "Can not use the dashboard resources",
            id="wrong-key",
        ),
    ],
)
async def test_resource_handler_wrong_store(
    hass: HomeAssistant,
    installed_plugin: PluginRepository,
    caplog: pytest.LogCaptureFixture,
    attribute: str,
    value: Any,
    message: str,
) -> None:
    """Test a dashboard resource store the Marketplace does not recognise."""
    setattr(hass.data["lovelace"].resources.store, attribute, value)

    assert installed_plugin._get_resource_handler() is None
    assert message in caplog.text


async def test_resource_handler_yaml_mode(
    hass: HomeAssistant,
    installed_plugin: PluginRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that YAML mode dashboards have no resources to update."""
    hass.data["lovelace"].resources.store = None

    assert installed_plugin._get_resource_handler() is None
    assert "YAML mode detected, can not update resources" in caplog.text


async def test_resource_handler_without_lovelace(
    hass: HomeAssistant,
    installed_plugin: PluginRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the dashboard integration not being loaded at all."""
    del hass.data["lovelace"]

    assert installed_plugin._get_resource_handler() is None
    assert "Can not access the lovelace integration data" in caplog.text


async def test_add_dashboard_resource(
    installed_plugin: PluginRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Test registering the dashboard resource of a plugin."""
    resources = installed_plugin._get_resource_handler()
    resources.data.clear()

    await installed_plugin.update_dashboard_resources()

    assert [resource["url"] for resource in resources.async_items()] == [
        installed_plugin.generate_dashboard_resource_url()
    ]
    assert (
        "Adding dashboard resource"
        " /local/community/plugin-basic/plugin-basic.js?v=1296267-1.0.0" in caplog.text
    )


async def test_update_dashboard_resource(
    installed_plugin: PluginRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a new version replaces the registered dashboard resource."""
    resources = installed_plugin._get_resource_handler()
    previous_url = installed_plugin.generate_dashboard_resource_url()
    assert [resource["url"] for resource in resources.async_items()] == [previous_url]

    installed_plugin.data.installed_version = "1.1.0"
    await installed_plugin.update_dashboard_resources()

    assert (
        "Updating existing dashboard resource from"
        " /local/community/plugin-basic/plugin-basic.js?v=1296267-1.0.0 to"
        " /local/community/plugin-basic/plugin-basic.js?v=1296267-1.1.0" in caplog.text
    )
    assert [resource["url"] for resource in resources.async_items()] == [
        installed_plugin.generate_dashboard_resource_url()
    ]


@pytest.mark.parametrize(
    "module_url",
    [
        pytest.param("/local/community/plugin-basic/plugin-basic.js", id="local"),
        pytest.param("/hacsfiles/plugin-basic/plugin-basic.js", id="legacy_path"),
    ],
)
async def test_no_dashboard_resource_for_extra_modules(
    hass: HomeAssistant, installed_plugin: PluginRepository, module_url: str
) -> None:
    """Test a plugin the frontend loads as an extra module gets no resource."""
    resources = installed_plugin._get_resource_handler()
    resources.data.clear()
    extra_modules = UrlManager(lambda *_: None, [module_url])

    with patch.dict(hass.data, {DATA_EXTRA_MODULE_URL: extra_modules}):
        await installed_plugin.update_dashboard_resources()

    assert resources.async_items() == []


async def test_remove_dashboard_resource(
    installed_plugin: PluginRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that removing a plugin unregisters its dashboard resource."""
    resources = installed_plugin._get_resource_handler()
    assert len(resources.async_items()) == 1

    await installed_plugin.remove_dashboard_resources()

    assert (
        "Removing dashboard resource"
        " /local/community/plugin-basic/plugin-basic.js?v=1296267-1.0.0" in caplog.text
    )
    assert resources.async_items() == []


async def test_remove_every_dashboard_resource_of_the_plugin(
    installed_plugin: PluginRepository,
) -> None:
    """Test that a resource added twice by hand is removed twice."""
    resources = installed_plugin._get_resource_handler()
    await resources.async_create_item(
        {"res_type": "module", "url": "/local/community/plugin-basic/extra.js"}
    )
    assert len(resources.async_items()) == 2

    await installed_plugin.remove_dashboard_resources()

    assert resources.async_items() == []


async def test_dashboard_resources_ignore_prefix_matches(
    installed_plugin: PluginRepository,
) -> None:
    """Test that a plugin whose name is a prefix of another is left alone."""
    resources = installed_plugin._get_resource_handler()
    resources.data.clear()

    other_url = "/local/community/plugin-basic-extra/plugin-basic-extra.js?v=42100"
    await resources.async_create_item({"res_type": "module", "url": other_url})

    await installed_plugin.update_dashboard_resources()
    assert sorted(resource["url"] for resource in resources.async_items()) == sorted(
        [other_url, installed_plugin.generate_dashboard_resource_url()]
    )

    await installed_plugin.remove_dashboard_resources()
    assert [resource["url"] for resource in resources.async_items()] == [other_url]


@pytest.mark.parametrize(
    ("key", "value", "updated"),
    [
        pytest.param("country", ["NO"], "SE", id="country"),
        pytest.param("render_readme", True, False, id="render_readme"),
    ],
)
def test_manifest_key_ignored(key: str, value: Any, updated: Any) -> None:
    """Test a key of an existing hacs.json that is accepted, but ignored."""
    manifest = RepositoryManifest.from_dict({"name": "TEST", key: value})
    manifest.update_data({key: updated})

    assert manifest.manifest == {"name": "TEST"}
    assert not hasattr(manifest, key)


async def test_uninstall_without_a_domain(marketplace: MarketplaceManager) -> None:
    """Test that an integration without a domain can not be removed."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.domain = None

    with pytest.raises(MarketplaceError, match="Could not remove"):
        await repository.uninstall()


async def test_repository_manifest_of_a_removed_version(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test the manifest of a version that has no hacs.json."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    url = f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/3.0.0/hacs.json"
    response_mocker.add(url, mocked_response(url, status=HTTPStatus.NOT_FOUND))

    assert await repository.get_repository_manifest(version="3.0.0") is None


async def test_ensure_install_capabilities_rejects_new_core_requirement(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test refusing a version that needs a newer Home Assistant."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    url = f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/3.0.0/hacs.json"
    response_mocker.add(
        url,
        mocked_response(
            url, content=json.dumps({"homeassistant": "9999.99.99"}).encode()
        ),
    )

    with pytest.raises(
        MarketplaceError,
        match="This version requires Home Assistant 9999.99.99 or newer",
    ):
        await repository.async_install_repository(ref="3.0.0")


async def _install(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, repository_id: str
) -> dict[str, Any]:
    """Install a repository the way the panel does, return the answer."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "marketplace/repository/install", "repository": repository_id}
    )
    return await client.receive_json()


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_install_from_the_catalog(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test installing the version the catalog names skips the GitHub API."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    aioclient_mock.mock_calls.clear()

    assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    assert repository.data.installed_version == category_test_data["version_base"]
    assert not github_api_calls(aioclient_mock)
    assert_api_usage(aioclient_mock, snapshot)


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_install_custom_repository(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a repository outside the catalog installs through the GitHub API."""
    repository = marketplace.repositories.get_by_full_name(
        category_test_data["repository"]
    )
    aioclient_mock.mock_calls.clear()

    with patch.object(marketplace.repositories, "is_default", return_value=False):
        assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    assert repository.data.installed_version == category_test_data["version_base"]
    assert github_api_calls(aioclient_mock)
    assert_api_usage(aioclient_mock, snapshot)


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize(
    ("is_default", "progress"),
    [
        pytest.param(True, [10, 20, 30, 40, 50, 70, 80, 90, False], id="catalog"),
        # Without releases there is no version to resolve first
        pytest.param(False, [30, 40, 50, 70, 80, 90, False], id="github_api"),
    ],
)
async def test_install_reports_its_progress(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    is_default: bool,
    progress: list[int | bool],
) -> None:
    """Test an install reports each step once and ends its progress once."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    with (
        patch.object(marketplace.repositories, "is_default", return_value=is_default),
        patch.object(
            marketplace, "async_dispatch", wraps=marketplace.async_dispatch
        ) as dispatch,
    ):
        assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    assert [
        call.args[1]["progress"]
        for call in dispatch.call_args_list
        if call.args[0] == MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS
    ] == progress


@pytest.mark.parametrize("github_token", [None])
async def test_failed_version_lookup_ends_the_progress(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test an install failing before it writes anything is no longer running."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.releases = True

    with (
        patch.object(marketplace.repositories, "is_default", return_value=False),
        patch.object(
            repository, "update_repository", side_effect=MarketplaceError("Busy")
        ),
        patch.object(
            marketplace, "async_dispatch", wraps=marketplace.async_dispatch
        ) as dispatch,
    ):
        assert not (await _install(hass, hass_ws_client, repository.data.id))["success"]

    assert [
        call.args[1]["progress"]
        for call in dispatch.call_args_list
        if call.args[0] == MarketplaceSignal.REPOSITORY_INSTALL_PROGRESS
    ] == [10, False]


def _archive_without_content(repository: str) -> bytes:
    """Return an archive that leaves the content out, like export-ignore does."""
    return _zip_bytes({f"{repository.split('/')[1]}-1.0.0/README.md": ""})


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize(
    ("repository_name", "url", "response", "expected_files"),
    [
        pytest.param(
            REPOSITORY_INTEGRATION,
            f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/1.0.0/hacs.json",
            {"status": HTTPStatus.NOT_FOUND},
            ["custom_components/example/manifest.json"],
            id="no-hacs-json",
        ),
        pytest.param(
            REPOSITORY_INTEGRATION,
            f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/1.0.0"
            "/custom_components/example/manifest.json",
            {"status": HTTPStatus.NOT_FOUND},
            ["custom_components/example/manifest.json"],
            id="no-manifest-json",
        ),
        pytest.param(
            REPOSITORY_INTEGRATION,
            f"https://github.com/{REPOSITORY_INTEGRATION}/archive/refs/tags/1.0.0.zip",
            {"content": b"not a zip archive"},
            ["custom_components/example/manifest.json"],
            id="broken-archive",
        ),
        pytest.param(
            REPOSITORY_INTEGRATION,
            f"https://github.com/{REPOSITORY_INTEGRATION}/archive/refs/tags/1.0.0.zip",
            {"content": _archive_without_content(REPOSITORY_INTEGRATION)},
            ["custom_components/example/manifest.json"],
            id="integration-not-in-archive",
        ),
        pytest.param(
            "hacs-test-org/theme-basic",
            "https://github.com/hacs-test-org/theme-basic/archive/refs/tags/1.0.0.zip",
            {"content": _archive_without_content("hacs-test-org/theme-basic")},
            ["themes/example/example.yaml"],
            id="theme-not-in-archive",
        ),
    ],
)
async def test_install_from_the_catalog_falls_back(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    aioclient_mock: AiohttpClientMocker,
    config_dir: Path,
    repository_name: str,
    url: str,
    response: dict[str, Any],
    expected_files: list[str],
) -> None:
    """Test a catalog version the archive can not resolve uses the GitHub API."""
    repository = marketplace.repositories.get_by_full_name(repository_name)
    # Served once, the API path after it gets the recorded response
    response_mocker.add(url, mocked_response(url, **response))
    aioclient_mock.mock_calls.clear()

    assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    assert repository.data.installed_version == "1.0.0"
    assert github_api_calls(aioclient_mock)
    assert _installed_files(config_dir) == expected_files


@pytest.mark.parametrize("github_token", [None])
async def test_install_from_the_catalog_archive_too_large(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
    config_dir: Path,
) -> None:
    """Test an archive over the limits is not extracted.

    The limits hold for the whole repository, the few files of the
    integration in it still come in one by one.
    """
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    aioclient_mock.mock_calls.clear()

    with patch(
        "homeassistant.components.marketplace.repositories.base.MAX_ARCHIVE_MEMBERS",
        2,
    ):
        assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    # The file by file download of the API path is all that is left
    assert github_api_calls(aioclient_mock)
    assert _installed_files(config_dir) == ["custom_components/example/manifest.json"]


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.parametrize(
    ("repository_name", "member", "installed_file"),
    [
        pytest.param(
            REPOSITORY_INTEGRATION,
            "integration-basic-1.0.0/custom_components/example/../../../escaped.py",
            "custom_components/example/__init__.py",
            id="extracted-directory",
        ),
        pytest.param(
            "hacs-test-org/theme-basic",
            "theme-basic-1.0.0/themes/../../../escaped.yaml",
            "themes/example/example.yaml",
            id="written-file",
        ),
    ],
)
async def test_install_from_the_catalog_escaping_member(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
    repository_name: str,
    member: str,
    installed_file: str,
) -> None:
    """Test an archive member can not write outside the repository."""
    repository = marketplace.repositories.get_by_full_name(repository_name)
    repository.data.installed = True

    # What is installed already has to survive the failed install
    installed = config_dir / installed_file
    installed.parent.mkdir(parents=True)
    installed.write_text("installed")

    url = f"https://github.com/{repository_name}/archive/refs/tags/1.0.0.zip"
    response_mocker.add(
        url,
        mocked_response(
            url,
            content=_zip_bytes(
                {
                    member.replace("../../../escaped", "example"): "",
                    member: "escaped",
                }
            ),
        ),
    )

    response = await _install(hass, hass_ws_client, repository.data.id)

    assert not response["success"]
    assert "is not inside" in caplog.text
    assert _installed_files(config_dir) == [installed_file]
    assert installed.read_text() == "installed"


@pytest.mark.parametrize("github_token", [None])
async def test_install_from_the_catalog_while_rate_limited(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
) -> None:
    """Test running out of anonymous API requests does not stop a catalog install."""
    for url in (
        f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}",
        f"https://api.github.com/repos/{REPOSITORY_INTEGRATION}/releases",
    ):
        response_mocker.add(
            url,
            mocked_response(
                url, status=HTTPStatus.FORBIDDEN, json_content=RATE_LIMITED
            ),
            keep=True,
        )
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    assert repository.data.installed_version == "1.0.0"
    assert not marketplace.system.disabled


@pytest.mark.parametrize("github_token", [None])
async def test_install_from_the_catalog_commit(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    aioclient_mock: AiohttpClientMocker,
    config_dir: Path,
) -> None:
    """Test a repository without releases installs the commit the catalog names."""
    repository = marketplace.repositories.get_by_full_name("hacs-test-org/theme-basic")
    repository.data.last_version = None
    repository.data.last_commit = "abc1234"

    for url, content in (
        (
            "https://raw.githubusercontent.com/hacs-test-org/theme-basic/abc1234/hacs.json",
            b'{"name": "Theme basic"}',
        ),
        (
            "https://github.com/hacs-test-org/theme-basic/archive/abc1234.zip",
            _zip_bytes({"theme-basic-abc1234/themes/example.yaml": ""}),
        ),
    ):
        response_mocker.add(url, mocked_response(url, content=content))
    aioclient_mock.mock_calls.clear()

    assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    assert repository.data.installed_commit == "abc1234"
    assert repository.data.installed_version is None
    assert repository.display_installed_version == "abc1234"
    assert not github_api_calls(aioclient_mock)
    assert _installed_files(config_dir) == ["themes/example/example.yaml"]


@pytest.mark.parametrize("github_token", [None])
async def test_install_from_the_catalog_zip_release(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    aioclient_mock: AiohttpClientMocker,
    config_dir: Path,
) -> None:
    """Test an integration shipping a ZIP release installs the release asset."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    for url, content in (
        (
            f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/1.0.0/hacs.json",
            b'{"name": "Integration", "zip_release": true, "filename": "example.zip"}',
        ),
        (
            f"https://github.com/{REPOSITORY_INTEGRATION}/releases/download/1.0.0/example.zip",
            _zip_bytes(
                {
                    "__init__.py": "",
                    "manifest.json": '{"domain": "example", "name": "Example",'
                    ' "version": "1.0.0"}',
                }
            ),
        ),
    ):
        response_mocker.add(url, mocked_response(url, content=content))
    aioclient_mock.mock_calls.clear()

    assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    assert not github_api_calls(aioclient_mock)
    assert _installed_files(config_dir) == [
        "custom_components/example/__init__.py",
        "custom_components/example/manifest.json",
    ]


@pytest.mark.parametrize("github_token", [None])
async def test_install_from_the_catalog_release_assets(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    aioclient_mock: AiohttpClientMocker,
    config_dir: Path,
) -> None:
    """Test a dashboard resource shipped as a release asset lists the assets."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    asset_url = f"https://github.com/{REPOSITORY_PLUGIN}/releases/download/1.0.0/plugin-basic.js"
    map_url = f"{asset_url}.map"
    release_url = (
        f"https://api.github.com/repos/{REPOSITORY_PLUGIN}/releases/tags/1.0.0"
    )
    response_mocker.add(asset_url, mocked_response(asset_url, content=b"asset"))
    response_mocker.add(map_url, mocked_response(map_url, content=b"map"))
    response_mocker.add(
        release_url,
        mocked_response(
            release_url,
            json_content={
                "assets": [
                    {"name": "plugin-basic.js", "browser_download_url": asset_url},
                    {"name": "plugin-basic.js.map", "browser_download_url": map_url},
                ]
            },
        ),
    )
    aioclient_mock.mock_calls.clear()

    assert (await _install(hass, hass_ws_client, repository.data.id))["success"]

    # Only the API lists every asset of a release
    assert github_api_calls(aioclient_mock) == [URL(release_url)]
    # The probe already fetched the resource, the install reuses it
    requested = [call[1] for call in aioclient_mock.mock_calls]
    assert requested.count(URL(asset_url)) == 1
    assert repository.content.path.remote == "release"
    assert _installed_files(config_dir) == [
        "www/community/plugin-basic/plugin-basic.js",
        "www/community/plugin-basic/plugin-basic.js.gz",
        "www/community/plugin-basic/plugin-basic.js.map",
    ]


@pytest.mark.parametrize("github_token", [None])
async def test_install_from_the_catalog_release_assets_over_the_limit(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    aioclient_mock: AiohttpClientMocker,
    config_dir: Path,
) -> None:
    """Test a release whose assets are too large together is not installed."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    asset_url = f"https://github.com/{REPOSITORY_PLUGIN}/releases/download/1.0.0/plugin-basic.js"
    other_url = f"{asset_url}.map"
    release_url = (
        f"https://api.github.com/repos/{REPOSITORY_PLUGIN}/releases/tags/1.0.0"
    )
    response_mocker.add(asset_url, mocked_response(asset_url, content=b"asset"))
    response_mocker.add(
        release_url,
        mocked_response(
            release_url,
            json_content={
                "assets": [
                    {
                        "name": "plugin-basic.js",
                        "browser_download_url": asset_url,
                        "size": 600,
                    },
                    {
                        "name": "plugin-basic.js.map",
                        "browser_download_url": other_url,
                        "size": 600,
                    },
                ]
            },
        ),
    )
    aioclient_mock.mock_calls.clear()

    with patch(
        "homeassistant.components.marketplace.repositories.base.MAX_DOWNLOAD_SIZE",
        1000,
    ):
        response = await _install(hass, hass_ws_client, repository.data.id)

    assert not response["success"]
    assert "larger than the 1000 byte limit" in response["error"]["message"]
    assert URL(other_url) not in [call[1] for call in aioclient_mock.mock_calls]
    assert repository.data.installed is False
    assert _installed_files(config_dir) == []


@pytest.mark.parametrize("github_token", [None])
async def test_install_from_the_catalog_release_assets_rate_limited(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test running out of anonymous requests fails only the install."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    asset_url = f"https://github.com/{REPOSITORY_PLUGIN}/releases/download/1.0.0/plugin-basic.js"
    release_url = (
        f"https://api.github.com/repos/{REPOSITORY_PLUGIN}/releases/tags/1.0.0"
    )
    response_mocker.add(asset_url, mocked_response(asset_url, content=b"asset"))
    response_mocker.add(
        release_url,
        mocked_response(
            release_url, status=HTTPStatus.FORBIDDEN, json_content=RATE_LIMITED
        ),
    )

    response = await _install(hass, hass_ws_client, repository.data.id)

    assert not response["success"]
    assert response["error"]["code"] == "github_rate_limited"
    assert not marketplace.system.disabled
    assert repository.data.installed is False
    assert _installed_files(config_dir) == []


@pytest.mark.parametrize("github_token", [None])
async def test_install_from_the_catalog_requires_newer_core(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    hass_ws_client: WebSocketGenerator,
    response_mocker: MarketplaceResponses,
    config_dir: Path,
) -> None:
    """Test the catalog version is refused when it needs a newer Home Assistant."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    url = f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/1.0.0/hacs.json"
    response_mocker.add(
        url,
        mocked_response(url, content=b'{"name": "New", "homeassistant": "9999.1.0"}'),
    )

    response = await _install(hass, hass_ws_client, repository.data.id)

    assert not response["success"]
    assert response["error"]["message"] == (
        f"Installing {REPOSITORY_INTEGRATION} failed: This version requires"
        " Home Assistant 9999.1.0 or newer."
    )
    assert repository.data.installed is False
    assert _installed_files(config_dir) == []


async def test_theme_with_content_in_the_root_is_valid(
    marketplace: MarketplaceManager,
) -> None:
    """Test a theme in the root, as hacs.json says, needs no themes folder."""
    repository = ThemeRepository(marketplace, "owner/theme")
    repository.repository_manifest.content_in_root = True
    repository.treefiles = ["hacs.json", "theme.yaml"]

    with patch.object(repository, "common_validate", AsyncMock()):
        assert await repository.validate_repository()


def test_resource_url_keeps_the_file_name_whole(
    marketplace: MarketplaceManager,
) -> None:
    """Test a file name with URL characters does not lose its end to a fragment."""
    repository = PluginRepository(marketplace, "owner/card")
    repository.data.id = "8004"
    repository.data.file_name = "card#1?.js"
    repository.data.installed_version = "1.0.0"

    assert repository.generate_dashboard_resource_url().startswith(
        "/local/community/card/card%231%3F.js?v="
    )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        pytest.param("v1.0.0-beta.1", "v1.0.0-rc.1", id="beta_and_rc"),
        pytest.param("1.2.3", "12.3", id="same_digits"),
    ],
)
def test_resource_url_differs_per_version(
    marketplace: MarketplaceManager, first: str, second: str
) -> None:
    """Test two versions never share the address browsers cache a card by."""
    repository = PluginRepository(marketplace, "owner/card")
    repository.data.id = "8004"
    repository.data.file_name = "card.js"

    repository.data.installed_version = first
    url = repository.generate_dashboard_resource_url()
    repository.data.installed_version = second

    assert repository.generate_dashboard_resource_url() != url
