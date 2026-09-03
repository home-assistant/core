"""Tests for the Community store data handler."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.store.base import HacsBase, HacsRepositories
from homeassistant.components.store.const import DOMAIN
from homeassistant.components.store.repositories.base import HacsRepository
from homeassistant.components.store.utils.data import HacsData
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .const import REPOSITORY_INTEGRATION, REPOSITORY_INTEGRATION_ID

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
async def test_write_downloaded_repository(
    store: HacsBase,
    mock_repository: HacsRepository,
    hass_storage: dict[str, Any],
) -> None:
    """Test a downloaded repository ends up in the stored data."""
    mock_repository.data.category = "integration"
    mock_repository.data.installed = True
    mock_repository.data.installed_version = "1"
    store.repositories.register(mock_repository)

    await store.data.async_write()

    stored = hass_storage[f"{DOMAIN}.repositories"]["data"]
    assert stored[str(mock_repository.data.id)]["installed"] is True
    assert stored[str(mock_repository.data.id)]["version_installed"] == "1"


@pytest.mark.usefixtures("stored_repositories", "init_integration")
async def test_write_without_repositories(
    store: HacsBase,
    hass_storage: dict[str, Any],
) -> None:
    """Test writing with nothing registered empties the stored data."""
    assert hass_storage[f"{DOMAIN}.repositories"]["data"]

    store.system.disabled_reason = None
    store.repositories = HacsRepositories()

    await store.data.async_write()

    assert hass_storage[f"{DOMAIN}.repositories"]["data"] == {}


@pytest.mark.usefixtures("init_integration")
async def test_restore(
    store: HacsBase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test restoring registers the repositories and their attributes."""
    data = HacsData(store)

    with patch(
        "homeassistant.components.store.utils.data.async_load_from_storage",
        side_effect=_mocked_repositories,
    ):
        assert await data.restore()

    integration = store.repositories.get_by_id("1296269")
    assert integration is store.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    assert integration.data.show_beta is True
    assert integration.data.installed is True

    assert store.repositories.get_by_id("1296267").data.installed is False

    assert store.status.new is False
    assert "Loading base repository information" not in caplog.text


@pytest.mark.usefixtures("init_integration")
async def test_restore_skips_placeholder_repository(store: HacsBase) -> None:
    """Test the placeholder repository id is not restored."""
    data = HacsData(store)

    async def mocked_load(hass: HomeAssistant, key: str) -> Any:
        """Return a stored repository carrying the placeholder id."""
        if key != "repositories":
            return {}
        return {"0": {"category": "integration", "full_name": "test/test"}}

    with patch(
        "homeassistant.components.store.utils.data.async_load_from_storage",
        side_effect=mocked_load,
    ):
        assert await data.restore()

    assert store.repositories.get_by_id("0") is None


@pytest.mark.usefixtures("init_integration")
async def test_restore_unreadable_data(
    store: HacsBase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unreadable repositories file fails the restore."""
    data = HacsData(store)

    with patch(
        "homeassistant.components.store.utils.data.async_load_from_storage",
        side_effect=HomeAssistantError("Not valid JSON"),
    ):
        assert not await data.restore()

    assert "restore the file from a backup" in caplog.text


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
