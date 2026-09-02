"""Tests for the Community store setup."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.store.const import DOMAIN, VERSION_STORAGE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_api_usage, get_hacs, setup_integration
from .const import (
    REPOSITORY_INTEGRATION,
    REPOSITORY_INTEGRATION_ID,
    REPOSITORY_PLUGIN,
    REPOSITORY_PLUGIN_ID,
)

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def stored_repositories(hass_storage: dict[str, Any]) -> None:
    """Seed the stored repositories with two downloaded repositories."""
    hass_storage[f"{DOMAIN}.repositories"] = {
        "version": VERSION_STORAGE,
        "data": load_json_object_fixture("stored_repositories.json", DOMAIN),
    }


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry loads and unloads again."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not get_hacs(hass).system.disabled

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data


async def test_panel_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the store panel is registered while the config entry is loaded."""
    await setup_integration(hass, mock_config_entry)

    assert DOMAIN in hass.data["frontend_panels"]

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN not in hass.data["frontend_panels"]


@pytest.mark.usefixtures("stored_repositories")
async def test_entities_for_downloaded_repositories(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test each downloaded repository gets an update and a switch entity."""
    await setup_integration(hass, mock_config_entry)

    store = get_hacs(hass)
    assert {repo.data.full_name for repo in store.repositories.list_downloaded} == {
        REPOSITORY_INTEGRATION,
        REPOSITORY_PLUGIN,
    }

    # The platforms are set up concurrently, so the registry order is not fixed
    entities = sorted(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id),
        key=lambda entity: entity.entity_id,
    )
    assert [entity.entity_id for entity in entities] == [
        "switch.basic_integration_pre_release",
        "switch.basic_plugin_pre_release",
        "update.basic_integration_update",
        "update.basic_plugin_update",
    ]
    assert entities == snapshot(name="entities")

    assert hass.states.get("update.basic_integration_update") == snapshot(
        name="update_state"
    )


@pytest.mark.usefixtures("stored_repositories")
async def test_setup_request_volume(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting up does not make a request per known repository."""
    await setup_integration(hass, mock_config_entry)

    assert_api_usage(aioclient_mock, snapshot)


@pytest.mark.usefixtures("stored_repositories")
async def test_stored_repository_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the stored repository ids survive a restore."""
    await setup_integration(hass, mock_config_entry)

    store = get_hacs(hass)
    assert store.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    assert store.repositories.get_by_id(REPOSITORY_PLUGIN_ID)
