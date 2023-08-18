"""Tests for the Jellyfin integration."""
from unittest.mock import MagicMock

from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import async_load_json_fixture

from tests.common import MockConfigEntry
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


async def remove_device(
    ws_client: MockHAClientWebSocket, device_id: str, config_entry_id: str
) -> bool:
    """Remove config entry from a device."""
    await ws_client.send_json(
        {
            "id": 1,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": config_entry_id,
            "device_id": device_id,
        }
    )
    response = await ws_client.receive_json()
    return response["success"]


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test the Jellyfin configuration entry not ready."""
    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass,
        "auth-connect-address-failure.json",
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test the Jellyfin integration handling invalid credentials."""
    mock_client.auth.connect_to_address.return_value = await async_load_json_fixture(
        hass,
        "auth-connect-address.json",
    )
    mock_client.auth.login.return_value = await async_load_json_fixture(
        hass,
        "auth-login-failure.json",
    )

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
) -> None:
    """Test the Jellyfin configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_remove_devices(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_jellyfin: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={
            (
                DOMAIN,
                "DEVICE-UUID",
            )
        },
    )
    assert (
        await remove_device(
            await hass_ws_client(hass), device_entry.id, mock_config_entry.entry_id
        )
        is False
    )
    old_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "OLD-DEVICE-UUID")},
    )
    assert (
        await remove_device(
            await hass_ws_client(hass), old_device_entry.id, mock_config_entry.entry_id
        )
        is True
    )
