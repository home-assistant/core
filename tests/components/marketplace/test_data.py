"""Tests for the Marketplace data handler."""

from pathlib import Path
import shutil
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.marketplace.base import MarketplaceManager, Repositories
from homeassistant.components.marketplace.const import DOMAIN, STORAGE_VERSION
from homeassistant.components.marketplace.enums import DisabledReason
from homeassistant.components.marketplace.repositories.base import Repository
from homeassistant.components.marketplace.utils.data import MarketplaceData
from homeassistant.components.marketplace.utils.storage import async_load_from_storage
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import create_install_folders, setup_integration
from .const import (
    REPOSITORY_INTEGRATION,
    REPOSITORY_INTEGRATION_ID,
    REPOSITORY_PLUGIN_ID,
)

from tests.common import MockConfigEntry

RESTORED_REPOSITORIES = {
    "1296269": {
        "category": "integration",
        "full_name": "hacs-test-org/integration-basic",
        "installed": True,
        "show_beta": True,
    },
    "1296267": {
        "category": "plugin",
        "full_name": "hacs-test-org/plugin-basic",
        "installed": False,
    },
}


async def _mocked_repositories(hass: HomeAssistant, key: str) -> Any:
    """Return the restored repositories, and nothing for the other keys."""
    return RESTORED_REPOSITORIES if key == "repositories" else {}


@pytest.mark.usefixtures("init_integration")
async def test_write_installed_repository(
    marketplace: MarketplaceManager,
    mock_repository: Repository,
    hass_storage: dict[str, Any],
) -> None:
    """Test an installed repository ends up in the stored data."""
    mock_repository.data.category = "integration"
    mock_repository.data.installed = True
    mock_repository.data.installed_version = "1"
    marketplace.repositories.register(mock_repository)

    await marketplace.data.async_write()

    stored = hass_storage[f"{DOMAIN}.repositories"]["data"]
    assert stored[str(mock_repository.data.id)]["installed"] is True
    assert stored[str(mock_repository.data.id)]["version_installed"] == "1"


async def test_stored_data_is_a_copy(
    marketplace: MarketplaceManager, mock_repository: Repository
) -> None:
    """Test the stored data shares nothing the event loop keeps changing.

    It is encoded in the executor, a list changing meanwhile would break that.
    """
    mock_repository.data.category = "integration"
    mock_repository.data.installed = True
    mock_repository.data.topics = ["lights"]
    mock_repository.data.authors = ["@frenck"]
    marketplace.repositories.register(mock_repository)

    marketplace.data.async_store_repository_data(mock_repository)
    stored = marketplace.data.content[str(mock_repository.data.id)]

    assert stored["topics"] == ["lights"]
    assert stored["topics"] is not mock_repository.data.topics
    assert stored["authors"] is not mock_repository.data.authors
    assert (
        stored["repository_manifest"]
        is not mock_repository.repository_manifest.manifest
    )


@pytest.mark.usefixtures("stored_repositories", "init_integration")
async def test_write_without_repositories(
    marketplace: MarketplaceManager,
    hass_storage: dict[str, Any],
) -> None:
    """Test writing with nothing registered empties the stored data."""
    assert hass_storage[f"{DOMAIN}.repositories"]["data"]

    marketplace.system.disabled_reason = None
    marketplace.repositories = Repositories()

    await marketplace.data.async_write()

    assert hass_storage[f"{DOMAIN}.repositories"]["data"] == {}


@pytest.mark.usefixtures("init_integration")
async def test_restore(
    marketplace: MarketplaceManager,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test restoring registers the repositories and their attributes."""
    create_install_folders(config_dir, RESTORED_REPOSITORIES)
    data = MarketplaceData(marketplace)

    with patch(
        "homeassistant.components.marketplace.utils.data.async_load_from_storage",
        side_effect=_mocked_repositories,
    ):
        assert await data.restore()

    integration = marketplace.repositories.get_by_id("1296269")
    assert integration is marketplace.repositories.get_by_full_name(
        REPOSITORY_INTEGRATION
    )
    assert integration.data.show_beta is True
    assert integration.data.installed is True

    assert marketplace.repositories.get_by_id("1296267").data.installed is False

    assert marketplace.status.new is False
    assert "Loading base repository information" not in caplog.text


@pytest.mark.usefixtures("init_integration")
async def test_restore_skips_placeholder_repository(
    marketplace: MarketplaceManager,
) -> None:
    """Test the placeholder repository id is not restored."""
    data = MarketplaceData(marketplace)

    async def mocked_load(hass: HomeAssistant, key: str) -> Any:
        """Return a stored repository carrying the placeholder id."""
        if key != "repositories":
            return {}
        return {"0": {"category": "integration", "full_name": "test/test"}}

    with patch(
        "homeassistant.components.marketplace.utils.data.async_load_from_storage",
        side_effect=mocked_load,
    ):
        assert await data.restore()

    assert marketplace.repositories.get_by_id("0") is None


@pytest.mark.parametrize(
    "broken",
    [
        pytest.param(None, id="null"),
        pytest.param("an entry", id="string"),
        pytest.param({"category": "theme"}, id="no_full_name"),
        pytest.param(
            {"category": "theme", "full_name": "owner/theme", "last_fetched": 1e20},
            id="bad_timestamp",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_restore_skips_a_broken_entry(
    marketplace: MarketplaceManager,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
    broken: Any,
) -> None:
    """Test one stored repository that can not be restored leaves the rest alone."""
    create_install_folders(config_dir, RESTORED_REPOSITORIES)
    data = MarketplaceData(marketplace)

    async def mocked_load(hass: HomeAssistant, key: str) -> Any:
        """Return the stored repositories with a broken one among them."""
        if key != "repositories":
            return {}
        return RESTORED_REPOSITORIES | {"9999": broken}

    with patch(
        "homeassistant.components.marketplace.utils.data.async_load_from_storage",
        side_effect=mocked_load,
    ):
        assert await data.restore()

    assert marketplace.repositories.get_by_id("1296269").data.installed is True
    assert marketplace.repositories.get_by_id("9999") is None
    assert "Skipping stored repository 9999" in caplog.text


@pytest.mark.usefixtures("init_integration")
async def test_restore_names_the_legacy_file_it_could_not_read(
    marketplace: MarketplaceManager, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the file to restore is the one that could not be read, not ours."""
    data = MarketplaceData(marketplace)

    with patch(
        "homeassistant.components.marketplace.utils.data.async_load_from_storage",
        side_effect=HomeAssistantError(
            "Error while loading /config/.storage/hacs.hacs: unexpected character"
        ),
    ):
        assert not await data.restore()

    assert "/config/.storage/hacs.hacs" in caplog.text
    assert ".storage/marketplace.common" not in caplog.text


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param([["a list"]], id="list"),
        pytest.param(["a string"], id="string"),
        pytest.param(NotImplementedError, id="unknown_storage_version"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_restore_unusable_file(
    marketplace: MarketplaceManager,
    caplog: pytest.LogCaptureFixture,
    side_effect: Any,
) -> None:
    """Test a file that is not what the Marketplace wrote fails the restore."""
    data = MarketplaceData(marketplace)

    with patch(
        "homeassistant.components.marketplace.utils.data.async_load_from_storage",
        side_effect=side_effect,
    ):
        assert not await data.restore()

    assert ".storage/marketplace.common" in caplog.text


@pytest.mark.parametrize("unreadable", ["common", "repositories"])
@pytest.mark.usefixtures("init_integration")
async def test_restore_unreadable_data(
    marketplace: MarketplaceManager,
    caplog: pytest.LogCaptureFixture,
    unreadable: str,
) -> None:
    """Test an unreadable file fails the restore, it is not taken as empty."""
    data = MarketplaceData(marketplace)
    load = async_load_from_storage

    async def load_from_storage(hass: HomeAssistant, key: str) -> Any:
        if key == unreadable:
            raise HomeAssistantError("Not valid JSON")
        return await load(hass, key)

    with patch(
        "homeassistant.components.marketplace.utils.data.async_load_from_storage",
        load_from_storage,
    ):
        assert not await data.restore()

    assert "Not valid JSON" in caplog.text


@pytest.mark.parametrize(
    ("reason", "written"),
    [
        pytest.param(DisabledReason.RATE_LIMIT, True, id="rate_limit"),
        pytest.param(DisabledReason.INVALID_TOKEN, True, id="invalid_token"),
        pytest.param(DisabledReason.REMOVED, False, id="removed"),
    ],
)
@pytest.mark.usefixtures("stored_repositories", "init_integration")
async def test_write_while_disabled(
    marketplace: MarketplaceManager,
    hass_storage: dict[str, Any],
    reason: DisabledReason,
    written: bool,
) -> None:
    """Test an install while GitHub is out of reach is still saved."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed_version = "2.0.0"
    marketplace.disable(reason)

    await marketplace.data.async_write()

    stored = hass_storage[f"{DOMAIN}.repositories"]["data"][REPOSITORY_INTEGRATION_ID]
    assert (stored.get("version_installed") == "2.0.0") is written


@pytest.mark.usefixtures("stored_repositories")
async def test_write_on_unload(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading writes the restored data back out."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    stored = hass_storage[f"{DOMAIN}.repositories"]["data"]
    assert stored[REPOSITORY_INTEGRATION_ID]["full_name"] == REPOSITORY_INTEGRATION
    assert stored[REPOSITORY_INTEGRATION_ID]["installed"] is True


@pytest.mark.usefixtures("stored_repositories")
async def test_installs_deleted_by_hand_are_forgotten(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test what was deleted from disk no longer counts as installed."""
    shutil.rmtree(config_dir / "www" / "community" / "plugin-basic")

    await setup_integration(hass, mock_config_entry)
    marketplace = mock_config_entry.runtime_data

    plugin = marketplace.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    assert plugin.data.installed is False
    assert plugin.data.installed_version is None
    assert not entity_registry.async_get_entity_id(
        Platform.UPDATE, DOMAIN, REPOSITORY_PLUGIN_ID
    )

    # What is still on disk stays installed
    integration = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert integration.data.installed is True


@pytest.mark.usefixtures("stored_repositories")
async def test_broken_symlink_stays_installed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, config_dir: Path
) -> None:
    """Test a folder that is a symlink to something not there right now stays."""
    folder = config_dir / "www" / "community" / "plugin-basic"
    folder.rmdir()
    folder.symlink_to(config_dir / "not-mounted")

    await setup_integration(hass, mock_config_entry)

    plugin = mock_config_entry.runtime_data.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
    assert plugin.data.installed is True


@pytest.mark.parametrize(
    ("files_on_disk", "installed"),
    [
        pytest.param(["other.jinja", "example.jinja"], True, id="present"),
        pytest.param(["other.jinja"], False, id="deleted"),
    ],
)
async def test_template_deleted_by_hand(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    files_on_disk: list[str],
    installed: bool,
) -> None:
    """Test a template counts by its own file, not the folder it shares."""
    hass_storage[f"{DOMAIN}.repositories"] = {
        "version": STORAGE_VERSION,
        "data": {
            "1296268": {
                "category": "template",
                "full_name": "hacs-test-org/template-basic",
                "installed": True,
                "file_name": "example.jinja",
                "version_installed": "1.0.0",
            }
        },
    }
    templates = config_dir / "custom_templates"
    templates.mkdir()
    for name in files_on_disk:
        (templates / name).touch()

    await setup_integration(hass, mock_config_entry)

    template = mock_config_entry.runtime_data.repositories.get_by_id("1296268")
    assert template.data.installed is installed
