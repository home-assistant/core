"""Tests for the Community store setup."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.store import async_remove_config_entry_device
from homeassistant.components.store.const import DOMAIN, HACS_SYSTEM_ID
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import assert_api_usage, get_hacs, setup_integration
from .const import (
    REPOSITORY_INTEGRATION,
    REPOSITORY_INTEGRATION_ID,
    REPOSITORY_PLUGIN,
    REPOSITORY_PLUGIN_ID,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


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


@pytest.mark.parametrize(
    ("identifiers", "message"),
    [
        pytest.param(
            {("other_domain", "123456"), ("another_domain", "789")},
            "no valid HACS repository identifier found",
            id="other_domains_only",
        ),
        pytest.param(
            set(),
            "no valid HACS repository identifier found",
            id="no_identifiers",
        ),
        pytest.param(
            {(DOMAIN,), (DOMAIN, "123", "extra"), "not_a_tuple"},
            "no valid HACS repository identifier found",
            id="malformed_identifiers",
        ),
        pytest.param(
            {(DOMAIN, HACS_SYSTEM_ID)},
            "Cannot remove the service for HACS itself",
            id="system_device",
        ),
        pytest.param(
            {("other_domain", "789"), (DOMAIN, HACS_SYSTEM_ID)},
            "Cannot remove the service for HACS itself",
            id="system_device_among_others",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_remove_device_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    identifiers: set[Any],
    message: str,
) -> None:
    """Test removing a device that does not map to a repository is refused."""
    device_entry = MagicMock(spec=dr.DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = identifiers

    with pytest.raises(HomeAssistantError, match=message):
        await async_remove_config_entry_device(hass, mock_config_entry, device_entry)


@pytest.mark.parametrize(
    "identifiers",
    [
        pytest.param({(DOMAIN, "123456")}, id="single_identifier"),
        pytest.param(
            {("other_domain", "789"), (DOMAIN, "123456")},
            id="identifier_among_others",
        ),
        pytest.param({(DOMAIN, 123456)}, id="integer_identifier"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_remove_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    identifiers: set[Any],
) -> None:
    """Test removing a device for a repository that is not downloaded."""
    device_entry = MagicMock(spec=dr.DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = identifiers

    assert await async_remove_config_entry_device(hass, mock_config_entry, device_entry)


@pytest.mark.usefixtures("stored_repositories", "init_integration")
async def test_remove_device_still_downloaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a device for a downloaded repository is refused."""
    device_entry = MagicMock(spec=dr.DeviceEntry)
    device_entry.id = "test_device_id"
    device_entry.identifiers = {(DOMAIN, REPOSITORY_INTEGRATION_ID)}

    with pytest.raises(
        HomeAssistantError,
        match=f"Cannot remove service for {REPOSITORY_INTEGRATION}",
    ):
        await async_remove_config_entry_device(hass, mock_config_entry, device_entry)
