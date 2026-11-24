"""Tests for the Marstek integration."""

from dataclasses import replace
from ipaddress import IPv4Address
import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from aiomarstek import MarstekDeviceInfo
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.marstek.coordinator import MarstekDataUpdateCoordinator
from homeassistant.components.marstek.helpers import async_create_udp_client
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .conftest import MOCK_DEVICE_INFO

UNSUPPORTED_DEVICE_INFO = MarstekDeviceInfo(
    id=0,
    device_type="VenusE 2.0",
    version=1,
    wifi_name="TestWiFi",
    ip="192.168.1.100",
    wifi_mac="AA:BB:CC:DD:EE:FF",
    ble_mac="11:22:33:44:55:66",
    mac="AA:BB:CC:DD:EE:FF",
)


async def test_async_setup_entry_retries_when_client_creation_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entry setup retries when the shared UDP client cannot be created."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.marstek.helpers.async_create_udp_client",
        side_effect=OSError("network down"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_cleans_up_client_at_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test the shared UDP client is cleaned up when Home Assistant stops."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_udp_client.async_cleanup.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_udp_client.async_cleanup.assert_awaited_once()


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setting up a config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_udp_client.get_device_info.assert_awaited_once()


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test unloading a config entry keeps the shared UDP client alive."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_udp_client.async_cleanup.assert_not_awaited()


async def test_async_unload_multiple_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test the shared UDP client stays alive while entries are unloaded."""
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
    second_device_info = replace(
        MOCK_DEVICE_INFO, ip="192.168.1.101", mac="AA:BB:CC:DD:EE:00"
    )
    mock_udp_client.get_device_info.side_effect = lambda host: (
        second_device_info if host == "192.168.1.101" else MOCK_DEVICE_INFO
    )

    # Setting up the component loads all of its config entries.
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert second_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_udp_client.async_cleanup.assert_not_awaited()

    assert await hass.config_entries.async_unload(second_entry.entry_id)
    await hass.async_block_till_done()
    mock_udp_client.async_cleanup.assert_not_awaited()


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
    mock_udp_client.async_cleanup.assert_not_awaited()
    assert "Unexpected error fetching Marstek" not in caplog.text


async def test_async_setup_entry_without_stable_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setup retries when device information has no stable identifier."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_info.return_value = MarstekDeviceInfo(
        id=0,
        device_type="VenusE 3.0",
        version=1,
        wifi_name="TestWiFi",
        ip="192.168.1.100",
        wifi_mac="",
        ble_mac="",
        mac="",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_udp_client.async_cleanup.assert_not_awaited()


async def test_async_setup_entry_device_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setup retries when another device answers at the configured host."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_info.return_value = MarstekDeviceInfo(
        id=0,
        device_type="VenusE 3.0",
        version=1,
        wifi_name="TestWiFi",
        ip="192.168.1.100",
        wifi_mac="11:11:11:11:11:11",
        ble_mac="22:22:22:22:22:22",
        mac="11:11:11:11:11:11",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


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
    mock_udp_client.async_cleanup.assert_not_awaited()


async def test_async_setup_entry_first_refresh_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setup fails when the first refresh raises an error."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        MarstekDataUpdateCoordinator,
        "async_config_entry_first_refresh",
        new=AsyncMock(side_effect=ConfigEntryError("boom")),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_udp_client.async_cleanup.assert_not_awaited()


async def test_async_setup_entry_first_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setup retries when the first data refresh fails."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_status.side_effect = OSError("network down")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_udp_client.async_cleanup.assert_not_awaited()
