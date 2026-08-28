"""Tests for the Marstek integration."""

from ipaddress import IPv4Address
import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.marstek import async_create_udp_client
from homeassistant.components.marstek.coordinator import MarstekDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from tests.common import MockConfigEntry

UNSUPPORTED_DEVICE_INFO = {
    "id": 0,
    "device": "VenusE 2.0",
    "ver": 1,
    "wifi_name": "TestWiFi",
    "ip": "192.168.1.100",
    "wifi_mac": "AA:BB:CC:DD:EE:FF",
    "ble_mac": "11:22:33:44:55:66",
}


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
    assert isinstance(
        mock_config_entry.runtime_data.coordinator, MarstekDataUpdateCoordinator
    )
    assert mock_config_entry.runtime_data.coordinator.udp_client is mock_udp_client
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
        title="Marstek VNSD-0 v2 (192.168.1.101)",
        unique_id="AA:BB:CC:DD:EE:00",
        data={
            "host": "192.168.1.101",
            "mac": "AA:BB:CC:DD:EE:00",
            "device_type": "VNSD-0",
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
    assert mock_config_entry.runtime_data.coordinator.udp_client is mock_udp_client
    assert second_entry.runtime_data.coordinator.udp_client is mock_udp_client

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
    assert not hasattr(mock_config_entry, "runtime_data")


async def test_async_create_udp_client(
    hass: HomeAssistant,
) -> None:
    """Test creating a UDP client configures broadcast addresses."""
    with (
        patch(
            "homeassistant.components.marstek.helpers.MarstekUDPClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.marstek.helpers.network.async_get_ipv4_broadcast_addresses",
            return_value=[IPv4Address("192.168.1.255")],
        ),
    ):
        mock_client = mock_client_class.return_value
        mock_client.async_setup = AsyncMock()
        mock_client.async_cleanup = AsyncMock()

        client = await async_create_udp_client(hass)

    assert client is mock_client
    mock_client.async_setup.assert_awaited_once()
    cast(MagicMock, mock_client.set_broadcast_addresses).assert_called_once_with(
        ["192.168.1.255"]
    )
    mock_client.async_cleanup.assert_not_awaited()


async def test_async_create_udp_client_cleans_up_on_broadcast_lookup_failure(
    hass: HomeAssistant,
) -> None:
    """Test client creation cleans up when broadcast address lookup fails."""
    with (
        patch(
            "homeassistant.components.marstek.helpers.MarstekUDPClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.marstek.helpers.network.async_get_ipv4_broadcast_addresses",
            side_effect=OSError("network down"),
        ),
    ):
        mock_client = mock_client_class.return_value
        mock_client.async_setup = AsyncMock()
        mock_client.async_cleanup = AsyncMock()

        with pytest.raises(OSError):
            await async_create_udp_client(hass)

    mock_client.async_cleanup.assert_awaited_once()


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup retries when the device cannot be reached."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_info.side_effect = TimeoutError("timeout")

    with caplog.at_level(logging.ERROR):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_udp_client.async_cleanup.assert_awaited_once()
    assert "Unexpected error fetching Marstek" not in caplog.text


@pytest.mark.parametrize(
    "device_info",
    [
        pytest.param(None, id="invalid_data"),
        pytest.param({"ip": "192.168.1.100"}, id="missing_stable_id"),
    ],
)
async def test_async_setup_entry_invalid_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
    device_info: object,
) -> None:
    """Test setup retries when device information is invalid."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_info.return_value = device_info

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_udp_client.async_cleanup.assert_awaited_once()


async def test_async_setup_entry_unsupported_device_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setup fails when the device type is unsupported."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_info.return_value = UNSUPPORTED_DEVICE_INFO

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_udp_client.async_cleanup.assert_awaited_once()


async def test_async_setup_entry_cleans_up_after_first_refresh_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setup cleans up when the first refresh raises an error."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        MarstekDataUpdateCoordinator,
        "async_config_entry_first_refresh",
        new=AsyncMock(side_effect=ConfigEntryError("boom")),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
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
