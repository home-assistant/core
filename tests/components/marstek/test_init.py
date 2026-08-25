"""Tests for the Marstek integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.marstek.const import DOMAIN
from homeassistant.components.marstek.coordinator import MarstekDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setting up a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
    ) as mock_forward_entry_setups:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, MarstekDataUpdateCoordinator)
    assert mock_config_entry.runtime_data.udp_client is mock_udp_client
    mock_udp_client.get_device_info.assert_awaited_once()
    mock_forward_entry_setups.assert_awaited_once()


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test unloading a config entry cleans up its coordinator."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_udp_client.async_cleanup.assert_awaited_once()


async def test_async_unload_multiple_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test the shared UDP client is cleaned up only when the last entry unloads."""
    second_entry = MockConfigEntry(
        domain=mock_config_entry.domain,
        title="Marstek ES6 v2 (192.168.1.101)",
        unique_id="AA:BB:CC:DD:EE:00",
        data={
            "host": "192.168.1.101",
            "mac": "AA:BB:CC:DD:EE:00",
            "device_type": "ES6",
            "version": 2,
            "wifi_name": "OtherWiFi",
            "wifi_mac": "AA:BB:CC:DD:EE:00",
            "ble_mac": "11:22:33:44:55:77",
        },
    )
    mock_config_entry.add_to_hass(hass)
    second_entry.add_to_hass(hass)

    # Setting up the component loads all of its config entries.
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert second_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.udp_client is mock_udp_client
    assert second_entry.runtime_data.udp_client is mock_udp_client

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_udp_client.async_cleanup.assert_not_awaited()

    assert await hass.config_entries.async_unload(second_entry.entry_id)
    await hass.async_block_till_done()
    mock_udp_client.async_cleanup.assert_awaited_once()


async def test_async_setup_entry_client_creation_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the shared UDP client cannot be created."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.marstek.async_create_udp_client",
        side_effect=OSError("network down"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert DOMAIN not in hass.data


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setup retries when the device cannot be reached."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_info.side_effect = TimeoutError("timeout")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_udp_client.async_cleanup.assert_awaited_once()


async def test_async_setup_entry_cleans_up_after_first_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setup cleans up when the first data refresh fails."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_status.side_effect = OSError("network down")

    with patch.object(
        hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
    ) as mock_forward_entry_setups:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_udp_client.async_cleanup.assert_awaited_once()
    mock_forward_entry_setups.assert_not_awaited()
