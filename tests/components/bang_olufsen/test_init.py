"""Test the bang_olufsen __init__."""

from unittest.mock import AsyncMock

from aiohttp.client_exceptions import ServerTimeoutError
from mozart_api.models import PairedRemoteResponse

from homeassistant.components.bang_olufsen import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import (
    TEST_FRIENDLY_NAME,
    TEST_MODEL_BALANCE,
    TEST_REMOTE_SERIAL_PAIRED,
    TEST_SERIAL_NUMBER,
)
from .util import get_remote_entity_ids

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test async_setup_entry."""

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED

    # Load entry
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Check that the device has been registered properly
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_SERIAL_NUMBER)}
    )
    assert device is not None
    # Is usually TEST_NAME, but is updated to the device's friendly name by _update_name_and_beolink
    assert device.name == TEST_FRIENDLY_NAME
    assert device.model == TEST_MODEL_BALANCE

    # Ensure that the connection has been checked WebSocket connection has been initialized
    assert mock_mozart_client.check_device_connection.call_count == 1
    assert mock_mozart_client.close_api_client.call_count == 0
    assert mock_mozart_client.connect_notifications.call_count == 1


async def test_setup_entry_remote_unpaired(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test async_setup_entry where a remote has been unpaired and should be removed."""

    # Load entry
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check device and API call count (called once during init and once in async_setup_entry in event.py)
    assert mock_mozart_client.get_bluetooth_remotes.call_count == 2
    assert device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)})

    # Check entities
    for entity_id in get_remote_entity_ids():
        assert entity_registry.async_get(entity_id)

    # "Unpair" the remote and reload config_entry
    mock_mozart_client.get_bluetooth_remotes.return_value = PairedRemoteResponse(
        items=[]
    )
    hass.config_entries.async_schedule_reload(mock_config_entry.entry_id)

    # Check device and API call count
    assert mock_mozart_client.get_bluetooth_remotes.call_count == 4
    assert not device_registry.async_get_device({(DOMAIN, TEST_REMOTE_SERIAL_PAIRED)})

    # Check entities
    for entity_id in get_remote_entity_ids():
        assert not entity_registry.async_get(entity_id)


async def test_setup_entry_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test failed async_setup_entry."""

    # Set the device connection check to fail
    mock_mozart_client.check_device_connection.side_effect = ExceptionGroup(
        "", (ServerTimeoutError(), TimeoutError())
    )

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED

    # Load entry
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY

    # Ensure that the connection has been checked, API client correctly closed
    # and WebSocket connection has not been initialized
    assert mock_mozart_client.check_device_connection.call_count == 1
    assert mock_mozart_client.close_api_client.call_count == 1
    assert mock_mozart_client.connect_notifications.call_count == 0


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Test unload_entry."""

    # Load entry
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert hasattr(mock_config_entry, "runtime_data")

    # Unload entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    # Ensure WebSocket notification listener and REST API client have been closed
    assert mock_mozart_client.disconnect_notifications.call_count == 1
    assert mock_mozart_client.close_api_client.call_count == 1

    # Ensure that the entry is not loaded and has been removed from hass
    assert not hasattr(mock_config_entry, "runtime_data")
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
