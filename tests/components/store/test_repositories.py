"""Tests for the Community store repositories."""

from http import HTTPStatus
import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch
import zipfile

from aiogithubapi import GitHubReleaseAssetModel
from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel
from aiogithubapi.models.release import GitHubReleaseModel
from awesomeversion import AwesomeVersion
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.store.base import HacsBase, RemovedRepository
from homeassistant.components.store.enums import HacsCategory, HacsDispatchEvent
from homeassistant.components.store.exceptions import HacsException
from homeassistant.components.store.repositories.base import (
    HacsManifest,
    HacsRepository,
    RepositoryData,
)
from homeassistant.components.store.repositories.plugin import HacsPluginRepository
from homeassistant.components.store.utils.validate import Validate
from homeassistant.components.store.utils.workarounds import LegacyTreeFile
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component

from . import CategoryTestData, category_test_data_parametrized, mocked_response
from .conftest import StoreResponses
from .const import REPOSITORY_INTEGRATION, REPOSITORY_PLUGIN

from tests.common import async_mock_service
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def python_script_integration(hass: HomeAssistant, config_dir: Path) -> None:
    """Load the python script integration so its category is active."""
    (config_dir / "python_scripts").mkdir()
    assert await async_setup_component(hass, "python_script", {})


def _tree(*paths: tuple[str, bool]) -> list[LegacyTreeFile]:
    """Return a repository tree of (path, is_directory) pairs."""
    return [
        LegacyTreeFile(
            GitHubGitTreeEntryModel(
                {"path": path, "type": "tree" if directory else "blob"}
            ),
            "test/test",
            "main",
        )
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


def _downloaded_files(config_dir: Path) -> list[str]:
    """Return every file below the configuration directory, sorted."""
    return sorted(
        path.relative_to(config_dir).as_posix()
        for path in config_dir.rglob("*")
        if path.is_file()
    )


def test_manifest_defaults() -> None:
    """Test the defaults of a hacs.json that only carries a name."""
    manifest = HacsManifest.from_dict({"name": "TEST"})

    assert manifest.manifest == {"name": "TEST"}
    assert manifest.name == "TEST"
    assert manifest.content_in_root is False
    assert manifest.zip_release is False
    assert manifest.filename is None
    assert manifest.country == []
    assert manifest.homeassistant is None
    assert manifest.persistent_directory is None
    assert manifest.hacs is None
    assert manifest.hide_default_branch is False


def test_manifest_rejects_none() -> None:
    """Test that a missing hacs.json is not silently accepted."""
    with pytest.raises(HacsException):
        HacsManifest.from_dict(None)


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
        pytest.param({"reason": "Repository was removed from the store"}, id="reason"),
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
async def test_can_download(
    store: HacsBase, ha_version: str, required_version: str, expected: bool
) -> None:
    """Test whether a repository can be downloaded on this Home Assistant."""
    repository = HacsRepository(store)
    repository.data.releases = True
    repository.repository_manifest.homeassistant = required_version
    store.core.ha_version = AwesomeVersion(ha_version)

    assert repository.can_download is expected


async def test_can_download_without_requirement(store: HacsBase) -> None:
    """Test that a repository without a requirement can always be downloaded."""
    assert HacsRepository(store).can_download


async def test_display_status(store: HacsBase) -> None:
    """Test the status the frontend shows for a repository."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
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
    store.core.ha_version = AwesomeVersion("0.0.0")
    repository.repository_manifest.homeassistant = "1.0.0"
    assert repository.display_status == "pending-upgrade"

    repository.data.last_version = "1"
    assert repository.display_status == "installed"


async def test_pending_update(store: HacsBase) -> None:
    """Test when a repository counts as having an update pending."""
    repository = HacsRepository(store)
    store.core.ha_version = AwesomeVersion("0.109.0")
    repository.repository_manifest.homeassistant = "0.110.0"
    repository.data.releases = True
    assert not repository.pending_update

    repository = HacsRepository(store)
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
        pytest.param("dummy", "plugin", True, False, True, id="plugin-release"),
        pytest.param("main", "plugin", True, False, False, id="default-branch"),
        pytest.param("dummy", "integration", True, False, False, id="wrong-category"),
        pytest.param("dummy", "plugin", False, False, False, id="no-releases"),
        pytest.param("dummy", "plugin", False, True, True, id="zip-release"),
        pytest.param("main", "plugin", False, True, False, id="zip-release-branch"),
    ],
)
def test_should_try_releases(
    mock_repository: HacsRepository,
    ref: str,
    category: str,
    releases: bool,
    zip_release: bool,
    expected: bool,
) -> None:
    """Test when the store looks at releases instead of the repository tree."""
    mock_repository.ref = ref
    mock_repository.data.category = category
    mock_repository.data.releases = releases
    mock_repository.repository_manifest.zip_release = zip_release
    mock_repository.repository_manifest.filename = "test.zip" if zip_release else None

    assert mock_repository.should_try_releases is expected


def test_gather_files_to_download(mock_repository: HacsRepository) -> None:
    """Test gathering the files of a plain repository."""
    mock_repository.content.path.remote = ""
    mock_repository.tree = _tree(("test/path/file.file", False))

    assert [file.path for file in mock_repository.gather_files_to_download()] == [
        "test/path/file.file"
    ]


def test_gather_files_single_file_repository(mock_repository: HacsRepository) -> None:
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
    mock_repository_plugin: HacsRepository,
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
    mock_repository_plugin: HacsRepository,
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
    mock_repository_plugin: HacsRepository,
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
    mock_repository_plugin: HacsRepository,
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


def test_gather_zip_release(mock_repository_plugin: HacsRepository) -> None:
    """Test that a zip release only serves the archive."""
    mock_repository_plugin.data.file_name = "test.zip"
    mock_repository_plugin.repository_manifest.zip_release = True
    mock_repository_plugin.repository_manifest.filename = "test.zip"
    mock_repository_plugin.releases.objects = [
        GitHubReleaseModel({"tag_name": "3", "assets": [{"name": "test.zip"}]})
    ]

    files = [file.name for file in mock_repository_plugin.gather_files_to_download()]

    assert files == ["test.zip"]


def test_gather_theme_files_in_root(mock_repository_theme: HacsRepository) -> None:
    """Test that a theme in the repository root only takes one yaml file."""
    mock_repository_theme.repository_manifest.content_in_root = True
    mock_repository_theme.content.path.remote = ""
    mock_repository_theme.data.file_name = "test.yaml"
    mock_repository_theme.tree = _tree(
        ("test.yaml", False),
        ("dir", True),
        ("test2.yaml", False),
    )

    files = [file.path for file in mock_repository_theme.gather_files_to_download()]

    assert files == ["test.yaml"]


def test_gather_appdaemon_files(mock_repository_appdaemon: HacsRepository) -> None:
    """Test that an AppDaemon app takes everything below its apps directory."""
    mock_repository_appdaemon.tree = _tree(
        ("test.py", False),
        ("apps/test/test.py", False),
        ("apps/test/core/test.py", False),
        ("apps/test/devices/test.py", False),
        (".github/file.file", False),
    )

    files = [file.path for file in mock_repository_appdaemon.gather_files_to_download()]

    assert files == [
        "apps/test/test.py",
        "apps/test/core/test.py",
        "apps/test/devices/test.py",
    ]


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
    mock_repository: HacsRepository,
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
    mock_repository_plugin: HacsRepository,
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
    mock_repository_plugin: HacsRepository,
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
    mock_repository: HacsRepository, assets: list[GitHubReleaseAssetModel] | None
) -> None:
    """Test a release that carries no assets at all."""
    assert mock_repository._find_target_asset(assets) is None


async def test_download_count_from_release(store: HacsBase) -> None:
    """Test that the download count comes from the matching release asset."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
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

    await repository.common_update_data(force=True, skip_releases=True)

    assert repository.data.downloads == 2000


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        pytest.param("1.0.0", "Integration basic 1.0.0", id="known-version"),
        pytest.param("99.99.99", None, id="unknown-version"),
    ],
)
async def test_get_hacs_json(
    store: HacsBase, version: str, expected: str | None
) -> None:
    """Test reading the hacs.json of a specific version."""
    repository = HacsRepository(store)
    repository.data.full_name = REPOSITORY_INTEGRATION

    manifest = await repository.get_hacs_json(version=version)

    assert (manifest.name if manifest else None) == expected


async def test_get_hacs_json_swallows_exceptions(store: HacsBase) -> None:
    """Test that a broken hacs.json never propagates out."""
    repository = HacsRepository(store)
    repository.data.full_name = REPOSITORY_INTEGRATION

    with patch.object(
        repository, "get_hacs_json_raw", side_effect=Exception("Test exception")
    ):
        assert await repository.get_hacs_json(version="1.0.0") is None

    with patch(
        "homeassistant.components.store.repositories.base.HacsManifest.from_dict",
        side_effect=ValueError("Invalid manifest"),
    ):
        assert await repository.get_hacs_json(version="1.0.0") is None


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        pytest.param("1.0.0", {"name": "Integration basic 1.0.0"}, id="known-version"),
        pytest.param("99.99.99", None, id="unknown-version"),
    ],
)
async def test_get_hacs_json_raw(
    store: HacsBase, version: str, expected: dict[str, Any] | None
) -> None:
    """Test reading the raw hacs.json of a specific version."""
    repository = HacsRepository(store)
    repository.data.full_name = REPOSITORY_INTEGRATION

    assert await repository.get_hacs_json_raw(version=version) == expected


async def test_get_hacs_json_raw_swallows_exceptions(store: HacsBase) -> None:
    """Test that an unreadable hacs.json never propagates out."""
    repository = HacsRepository(store)
    repository.data.full_name = REPOSITORY_INTEGRATION

    with patch.object(store, "async_download_file", side_effect=Exception("boom")):
        assert await repository.get_hacs_json_raw(version="1.0.0") is None

    with patch(
        "homeassistant.components.store.repositories.base.json_loads_object",
        side_effect=ValueError("Invalid JSON"),
    ):
        assert await repository.get_hacs_json_raw(version="1.0.0") is None


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
    store: HacsBase, data: dict[str, Any], snapshot: SnapshotAssertion
) -> None:
    """Test which version of the documentation is served."""
    repository = HacsRepository(store)
    repository.data.full_name = REPOSITORY_INTEGRATION
    for key, value in data.items():
        setattr(repository.data, key, value)

    assert await repository.get_documentation(filename="README.md") == snapshot


async def test_get_documentation_without_filename(store: HacsBase) -> None:
    """Test that no filename means no documentation."""
    repository = HacsRepository(store)
    repository.data.full_name = REPOSITORY_INTEGRATION

    assert await repository.get_documentation() is None


async def test_get_documentation_without_version(store: HacsBase) -> None:
    """Test that a repository with nothing to point at has no documentation."""
    repository = HacsRepository(store)
    repository.data.full_name = REPOSITORY_INTEGRATION
    repository.ref = None

    assert await repository.get_documentation(filename="README.md") is None


@pytest.mark.parametrize(
    ("repository_full_name", "category"),
    [
        pytest.param(
            "hacs-test-org/integration-basic-custom",
            HacsCategory.INTEGRATION,
            id="integration",
        ),
        pytest.param(
            "hacs-test-org/plugin-custom-dist", HacsCategory.PLUGIN, id="plugin"
        ),
    ],
)
async def test_register_repository(
    hass: HomeAssistant,
    store: HacsBase,
    hass_ws_client: WebSocketGenerator,
    repository_full_name: str,
    category: HacsCategory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test adding a repository the store did not know about."""
    assert store.repositories.get_by_full_name(repository_full_name) is None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "store/repositories/add",
            "repository": repository_full_name,
            "category": category.value,
        }
    )
    assert (await client.receive_json())["success"]

    repository = store.repositories.get_by_full_name(repository_full_name)
    assert repository is not None

    await client.send_json_auto_id(
        {"type": "store/repository/info", "repository_id": repository.data.id}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == snapshot(exclude=props("local_path"))


@pytest.mark.parametrize(
    ("repository_full_name", "exception", "message"),
    [
        pytest.param(
            "home-assistant/core",
            "HomeAssistantCoreRepositoryException",
            "You can not add homeassistant/core, to use core integrations check the"
            " Home Assistant documentation for how to add them.",
            id="core",
        ),
        pytest.param(
            "home-assistant/addons",
            "AppRepositoryException",
            "The repository does not seem to be an integration, but an app"
            " repository. HACS does not manage apps.",
            id="core-addons",
        ),
        pytest.param(
            "hassio-addons/example",
            "AppRepositoryException",
            "The repository does not seem to be an integration, but an app"
            " repository. HACS does not manage apps.",
            id="addon-org",
        ),
        pytest.param(
            "hacs-test-org/addon-basic",
            "AppRepositoryException",
            "The repository does not seem to be an integration, but an app"
            " repository. HACS does not manage apps.",
            id="addon-repository",
        ),
        pytest.param(
            "hacs-test-org/integration-invalid",
            "HacsException",
            "<Integration hacs-test-org/integration-invalid> Repository structure"
            " for main is not compliant",
            id="not-compliant",
        ),
    ],
)
async def test_register_repository_failures(
    hass: HomeAssistant,
    store: HacsBase,
    hass_ws_client: WebSocketGenerator,
    repository_full_name: str,
    exception: str,
    message: str,
) -> None:
    """Test the errors reported when a repository can not be added."""
    messages: list[dict[str, Any]] = []
    async_dispatcher_connect(hass, HacsDispatchEvent.ERROR, messages.append)

    assert store.repositories.get_by_full_name(repository_full_name) is None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "store/repositories/add",
            "repository": repository_full_name,
            "category": HacsCategory.INTEGRATION.value,
        }
    )
    response = await client.receive_json()
    await hass.async_block_till_done()

    assert response["success"]
    assert response["result"] == {}
    assert store.repositories.get_by_full_name(repository_full_name) is None
    assert messages == [
        {"action": "add_repository", "exception": exception, "message": message}
    ]


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_validate_repository(
    store: HacsBase, category_test_data: CategoryTestData
) -> None:
    """Test validating the structure of a repository of every category."""
    repository = store.repositories.get_by_full_name(category_test_data["repository"])
    await repository.update_repository(force=True)

    assert await repository.validate_repository()
    assert repository.validate.errors == []


@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(
        categories=[
            HacsCategory.APPDAEMON,
            HacsCategory.PYTHON_SCRIPT,
            HacsCategory.TEMPLATE,
            HacsCategory.THEME,
        ]
    ),
)
async def test_validate_repository_without_content(
    store: HacsBase, category_test_data: CategoryTestData
) -> None:
    """Test that a repository without the expected content is refused."""
    repository = store.repositories.get_by_full_name(category_test_data["repository"])
    await repository.update_repository(force=True)

    repository.tree = _tree(("README.md", False))
    repository.treefiles = ["README.md"]

    with (
        patch.object(repository, "common_validate"),
        pytest.raises(HacsException, match="is not compliant"),
    ):
        await repository.validate_repository()


async def test_validate_integration_without_content(store: HacsBase) -> None:
    """Test an integration repository without a custom_components directory."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    await repository.update_repository(force=True)

    repository.tree = _tree(("README.md", False))
    repository.treefiles = ["README.md"]
    repository.content.path.remote = "custom_components"

    with (
        patch.object(repository, "common_validate"),
        pytest.raises(HacsException, match="is not compliant"),
    ):
        await repository.validate_repository()


async def test_validate_plugin_without_content(store: HacsBase) -> None:
    """Test a dashboard plugin repository without a script to serve."""
    repository = store.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    await repository.update_repository(force=True)

    repository.tree = _tree(("README.md", False))
    repository.treefiles = ["README.md"]
    repository.content.path.remote = None

    with (
        patch.object(repository, "common_validate"),
        pytest.raises(HacsException, match="is not compliant"),
    ):
        await repository.validate_repository()


@pytest.mark.parametrize(
    "category_test_data",
    category_test_data_parametrized(
        categories=[HacsCategory.PYTHON_SCRIPT, HacsCategory.THEME]
    ),
)
async def test_validate_repository_with_content_in_root(
    store: HacsBase, category_test_data: CategoryTestData
) -> None:
    """Test a repository that keeps its content in the repository root."""
    repository = store.repositories.get_by_full_name(category_test_data["repository"])
    await repository.update_repository(force=True)
    repository.repository_manifest.content_in_root = True

    # The common validation refetches the manifest, which would undo the change
    with patch.object(repository, "common_validate"):
        assert await repository.validate_repository()

    assert repository.content.path.remote == ""


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_update_repository_without_a_tree(
    store: HacsBase, category_test_data: CategoryTestData
) -> None:
    """Test that a refresh that finds no files keeps the known tree."""
    repository = store.repositories.get_by_full_name(category_test_data["repository"])
    await repository.update_repository(force=True)

    with patch.object(repository, "get_tree", return_value=[]):
        await repository.update_repository(ignore_issues=True, force=True)

    assert repository.tree


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_download_repository(
    hass: HomeAssistant,
    store: HacsBase,
    hass_ws_client: WebSocketGenerator,
    config_dir: Path,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test downloading a repository of every category."""
    repository = store.repositories.get_by_full_name(category_test_data["repository"])
    assert repository is not None
    assert repository.data.installed is False
    assert store.repositories.list_downloaded == []

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "store/repository/download", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]

    assert repository.data.installed is True
    assert repository.data.installed_version == category_test_data["version_base"]
    assert store.repositories.list_downloaded == [repository]
    assert _downloaded_files(config_dir) == snapshot


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_update_repository(
    hass: HomeAssistant,
    store: HacsBase,
    hass_ws_client: WebSocketGenerator,
    category_test_data: CategoryTestData,
) -> None:
    """Test downloading a specific newer version of a repository."""
    repository = store.repositories.get_by_full_name(category_test_data["repository"])
    assert repository is not None

    repository.data.installed = True
    repository.data.installed_version = category_test_data["version_base"]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "store/repository/download",
            "repository": repository.data.id,
            "version": category_test_data["version_update"],
        }
    )
    assert (await client.receive_json())["success"]

    assert repository.data.installed_version == category_test_data["version_update"]


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_remove_repository(
    hass: HomeAssistant,
    store: HacsBase,
    hass_ws_client: WebSocketGenerator,
    config_dir: Path,
    category_test_data: CategoryTestData,
) -> None:
    """Test removing a downloaded repository of every category."""
    repository = store.repositories.get_by_full_name(category_test_data["repository"])
    assert repository is not None

    repository.data.installed = True
    repository.data.file_name = category_test_data["files"][0]
    repository.content.path.local = repository.localpath

    for name in category_test_data["files"]:
        file = Path(repository.localpath, name)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()

    assert _downloaded_files(config_dir)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "store/repository/remove", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]

    assert repository.data.installed is False
    assert store.repositories.list_downloaded == []
    assert _downloaded_files(config_dir) == []


@pytest.mark.parametrize("category_test_data", category_test_data_parametrized())
async def test_repository_releases(
    hass: HomeAssistant,
    store: HacsBase,
    hass_ws_client: WebSocketGenerator,
    response_mocker: StoreResponses,
    category_test_data: CategoryTestData,
    snapshot: SnapshotAssertion,
) -> None:
    """Test listing the releases of a repository."""
    repository = store.repositories.get_by_full_name(category_test_data["repository"])
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
        {"type": "store/repository/releases", "repository_id": repository.data.id}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == snapshot


async def test_download_zip_release(
    store: HacsBase, response_mocker: StoreResponses, config_dir: Path
) -> None:
    """Test downloading a release that ships a zip archive."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
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
    assert _downloaded_files(config_dir) == [
        "custom_components/example/example/__init__.py",
        "custom_components/example/example/const.py",
    ]


async def test_download_zip_release_failure(
    store: HacsBase, response_mocker: StoreResponses
) -> None:
    """Test a zip release that can not be downloaded."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
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


async def test_download_repository_zip_without_ref(store: HacsBase) -> None:
    """Test that a repository archive needs something to download."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.ref = ""

    with pytest.raises(HacsException, match="Missing required elements"):
        await repository.download_repository_zip()


async def test_integration_restart_required_issue(
    hass: HomeAssistant,
    store: HacsBase,
    issue_registry: ir.IssueRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that downloading an integration asks for a restart."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "store/repository/download", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]

    assert repository.pending_restart is True
    assert issue_registry.async_get_issue(
        "store", f"restart_required_{repository.data.id}_{repository.ref}"
    )


async def test_integration_manifest_missing_key(store: HacsBase) -> None:
    """Test an integration manifest without a domain."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)

    with patch.object(
        repository, "async_get_integration_manifest", return_value={"name": "Example"}
    ):
        assert not await repository.validate_repository()

    assert repository.validate.errors == [
        "Missing expected key ''domain'' in manifest.json"
    ]


async def test_integration_manifest_missing_file(store: HacsBase) -> None:
    """Test an integration that has no manifest.json in its tree."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.tree = []

    with pytest.raises(HacsException, match="No manifest.json file found"):
        await repository.async_get_integration_manifest()


async def test_integration_manifest_for_version(
    store: HacsBase, response_mocker: StoreResponses
) -> None:
    """Test reading the integration manifest of a specific version."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    await repository.update_repository(force=True)

    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/1.0.0"
        "/custom_components/example/manifest.json"
    )
    response_mocker.add(url, mocked_response(url, json_content={"domain": "example"}))

    assert await repository.get_integration_manifest(version="1.0.0") == {
        "domain": "example"
    }


async def test_integration_manifest_for_missing_version(store: HacsBase) -> None:
    """Test the integration manifest of a version that was never published."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    await repository.update_repository(force=True)

    assert await repository.get_integration_manifest(version="99.99.99") is None


async def test_template_reloads_custom_templates(
    hass: HomeAssistant,
    store: HacsBase,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that removing a template repository reloads the custom templates."""
    repository = store.repositories.get_by_full_name("hacs-test-org/template-basic")
    repository.data.installed = True
    repository.data.file_name = "example.jinja"
    repository.content.path.local = repository.localpath

    file = Path(repository.localpath)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch()

    reloads = async_mock_service(hass, "homeassistant", "reload_custom_templates")

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "store/repository/remove", "repository": repository.data.id}
    )
    assert (await client.receive_json())["success"]

    assert len(reloads) == 1


@pytest.fixture
async def downloaded_plugin(store: HacsBase) -> HacsPluginRepository:
    """Return a downloaded dashboard plugin repository."""
    repository = store.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    await repository.async_install()
    return repository


@pytest.mark.parametrize(
    ("repository_name", "namespace"),
    [
        pytest.param(REPOSITORY_PLUGIN, "/hacsfiles/plugin-basic", id="basic"),
        pytest.param(
            "hacs-test-org/plugin-advanced",
            "/hacsfiles/plugin-advanced",
            id="advanced",
        ),
    ],
)
async def test_dashboard_namespace(
    downloaded_plugin: HacsPluginRepository, repository_name: str, namespace: str
) -> None:
    """Test the namespace a plugin serves its files under."""
    downloaded_plugin.data.full_name = repository_name

    assert downloaded_plugin.generate_dashboard_resource_namespace() == namespace


@pytest.mark.parametrize(
    ("downloaded", "selected", "available", "expected"),
    [
        pytest.param(None, None, None, "", id="nothing-known"),
        pytest.param("1.0.0", None, None, "100", id="downloaded"),
        pytest.param(None, "2.0.1", None, "201", id="selected"),
        pytest.param(None, None, "3.4.2", "342", id="available"),
        pytest.param("1.7-dev09-r2", None, None, "17092", id="non-numeric"),
    ],
)
async def test_dashboard_hacstag(
    downloaded_plugin: HacsPluginRepository,
    downloaded: str | None,
    selected: str | None,
    available: str | None,
    expected: str,
) -> None:
    """Test the cache busting tag of a dashboard resource."""
    downloaded_plugin.data.installed_commit = None
    downloaded_plugin.data.last_commit = None
    downloaded_plugin.data.installed_version = downloaded
    downloaded_plugin.data.last_version = available
    downloaded_plugin.data.selected_tag = selected

    assert (
        downloaded_plugin.generate_dashboard_resource_hacstag()
        == f"{downloaded_plugin.data.id}{expected}"
    )


async def test_dashboard_url(downloaded_plugin: HacsPluginRepository) -> None:
    """Test the URL a dashboard resource is registered with."""
    assert (
        downloaded_plugin.generate_dashboard_resource_url()
        == "/hacsfiles/plugin-basic/plugin-basic.js?hacstag=1296267100"
    )


async def test_dashboard_url_with_invalid_file_name(
    downloaded_plugin: HacsPluginRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a plugin pointing at a subdirectory is flattened and logged."""
    downloaded_plugin.data.file_name = "dist/plugin-basic.js"

    assert (
        downloaded_plugin.generate_dashboard_resource_url()
        == "/hacsfiles/plugin-basic/plugin-basic.js?hacstag=1296267100"
    )
    assert "have defined an invalid file name dist/plugin-basic.js" in caplog.text


async def test_resource_handler(downloaded_plugin: HacsPluginRepository) -> None:
    """Test that the dashboard resources are reachable in storage mode."""
    assert downloaded_plugin._get_resource_handler() is not None


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
    downloaded_plugin: HacsPluginRepository,
    caplog: pytest.LogCaptureFixture,
    attribute: str,
    value: Any,
    message: str,
) -> None:
    """Test a dashboard resource store the store does not recognise."""
    setattr(hass.data["lovelace"].resources.store, attribute, value)

    assert downloaded_plugin._get_resource_handler() is None
    assert message in caplog.text


async def test_resource_handler_yaml_mode(
    hass: HomeAssistant,
    downloaded_plugin: HacsPluginRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that YAML mode dashboards have no resources to update."""
    hass.data["lovelace"].resources.store = None

    assert downloaded_plugin._get_resource_handler() is None
    assert "YAML mode detected, can not update resources" in caplog.text


async def test_resource_handler_without_resources(
    hass: HomeAssistant,
    downloaded_plugin: HacsPluginRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a dashboard without any resource collection."""
    hass.data["lovelace"].resources = None

    assert downloaded_plugin._get_resource_handler() is None
    assert "Can not access the dashboard resources" in caplog.text


async def test_resource_handler_without_lovelace(
    hass: HomeAssistant,
    downloaded_plugin: HacsPluginRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the dashboard integration not being loaded at all."""
    del hass.data["lovelace"]

    assert downloaded_plugin._get_resource_handler() is None
    assert "Can not access the lovelace integration data" in caplog.text


async def test_add_dashboard_resource(
    downloaded_plugin: HacsPluginRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Test registering the dashboard resource of a plugin."""
    resources = downloaded_plugin._get_resource_handler()
    resources.data.clear()

    await downloaded_plugin.update_dashboard_resources()

    assert [resource["url"] for resource in resources.async_items()] == [
        downloaded_plugin.generate_dashboard_resource_url()
    ]
    assert (
        "Adding dashboard resource"
        " /hacsfiles/plugin-basic/plugin-basic.js?hacstag=1296267100" in caplog.text
    )


async def test_update_dashboard_resource(
    downloaded_plugin: HacsPluginRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a new version replaces the registered dashboard resource."""
    resources = downloaded_plugin._get_resource_handler()
    previous_url = downloaded_plugin.generate_dashboard_resource_url()
    assert [resource["url"] for resource in resources.async_items()] == [previous_url]

    downloaded_plugin.data.installed_version = "1.1.0"
    await downloaded_plugin.update_dashboard_resources()

    assert (
        "Updating existing dashboard resource from"
        " /hacsfiles/plugin-basic/plugin-basic.js?hacstag=1296267100 to"
        " /hacsfiles/plugin-basic/plugin-basic.js?hacstag=1296267110" in caplog.text
    )
    assert [resource["url"] for resource in resources.async_items()] == [
        downloaded_plugin.generate_dashboard_resource_url()
    ]


async def test_remove_dashboard_resource(
    downloaded_plugin: HacsPluginRepository, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that removing a plugin unregisters its dashboard resource."""
    resources = downloaded_plugin._get_resource_handler()
    assert len(resources.async_items()) == 1

    await downloaded_plugin.remove_dashboard_resources()

    assert (
        "Removing dashboard resource"
        " /hacsfiles/plugin-basic/plugin-basic.js?hacstag=1296267100" in caplog.text
    )
    assert resources.async_items() == []


async def test_dashboard_resources_ignore_prefix_matches(
    downloaded_plugin: HacsPluginRepository,
) -> None:
    """Test that a plugin whose name is a prefix of another is left alone."""
    resources = downloaded_plugin._get_resource_handler()
    resources.data.clear()

    other_url = "/hacsfiles/plugin-basic-extra/plugin-basic-extra.js?hacstag=42100"
    await resources.async_create_item({"res_type": "module", "url": other_url})

    await downloaded_plugin.update_dashboard_resources()
    assert sorted(resource["url"] for resource in resources.async_items()) == sorted(
        [other_url, downloaded_plugin.generate_dashboard_resource_url()]
    )

    await downloaded_plugin.remove_dashboard_resources()
    assert [resource["url"] for resource in resources.async_items()] == [other_url]


async def test_repository_ignored_by_country(mock_repository: HacsRepository) -> None:
    """Test that the configured country filters repositories out."""
    mock_repository.hacs.configuration.country = "ALL"
    assert not mock_repository.ignored_by_country_configuration

    mock_repository.repository_manifest.country = ["NO"]
    assert not mock_repository.ignored_by_country_configuration

    mock_repository.hacs.configuration.country = "SE"
    assert mock_repository.ignored_by_country_configuration

    mock_repository.hacs.configuration.country = "NO"
    assert not mock_repository.ignored_by_country_configuration


async def test_uninstall_without_a_domain(store: HacsBase) -> None:
    """Test that an integration without a domain can not be removed."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.domain = None

    with pytest.raises(HacsException, match="Could not uninstall"):
        await repository.uninstall()


async def test_hacs_json_of_a_removed_version(
    store: HacsBase, response_mocker: StoreResponses
) -> None:
    """Test the manifest of a version that has no hacs.json."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    url = f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/3.0.0/hacs.json"
    response_mocker.add(url, mocked_response(url, status=HTTPStatus.NOT_FOUND))

    assert await repository.get_hacs_json(version="3.0.0") is None


async def test_ensure_download_capabilities_rejects_new_core_requirement(
    store: HacsBase, response_mocker: StoreResponses
) -> None:
    """Test refusing a version that needs a newer Home Assistant."""
    repository = store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    url = f"https://raw.githubusercontent.com/{REPOSITORY_INTEGRATION}/3.0.0/hacs.json"
    response_mocker.add(
        url,
        mocked_response(
            url, content=json.dumps({"homeassistant": "9999.99.99"}).encode()
        ),
    )

    with pytest.raises(
        HacsException, match="This version requires Home Assistant 9999.99.99 or newer"
    ):
        await repository.async_download_repository(ref="3.0.0")
