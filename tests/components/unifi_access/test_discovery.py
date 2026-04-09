"""Tests for the UniFi Access discovery module."""

from __future__ import annotations

from unittest.mock import MagicMock

from unifi_discovery import UnifiDevice, UnifiService

from homeassistant.components.unifi_access.const import DOMAIN
from homeassistant.components.unifi_access.discovery import (
    async_discover_devices,
    async_start_discovery,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_HOST

from tests.common import MockConfigEntry


def _make_device(
    hw_addr: str = "b4:fb:e4:aa:bb:cc",
    source_ip: str = MOCK_HOST,
    access: bool = True,
) -> UnifiDevice:
    """Create a UnifiDevice for testing."""
    device = UnifiDevice(
        source_ip=source_ip,
        hw_addr=hw_addr,
        hostname="UDM-Pro",
        platform="UDMPRO",
    )
    device.services[UnifiService.Access] = access
    return device


async def test_trigger_discovery_creates_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_discovery: MagicMock,
) -> None:
    """Test that discovered Access devices trigger config flows."""
    device = _make_device(source_ip="10.0.0.99")
    mock_discovery.async_scan.return_value = [device]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1


async def test_trigger_discovery_skips_non_access(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_discovery: MagicMock,
) -> None:
    """Test that devices without Access service are skipped."""
    device = _make_device(access=False)
    mock_discovery.async_scan.return_value = [device]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0


async def test_trigger_discovery_skips_no_mac(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_discovery: MagicMock,
) -> None:
    """Test that devices without hw_addr are skipped."""
    device = _make_device(hw_addr="")
    mock_discovery.async_scan.return_value = [device]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 0


async def test_start_discovery_only_starts_once(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
) -> None:
    """Test that discovery is started only once."""
    async_start_discovery(hass)
    async_start_discovery(hass)
    await hass.async_block_till_done()

    mock_discovery.async_scan.assert_awaited_once()


async def test_async_discover_devices(
    mock_discovery: MagicMock,
) -> None:
    """Test async_discover_devices calls the scanner and returns results."""
    mock_device = _make_device()
    mock_discovery.async_scan.return_value = [mock_device]

    result = await async_discover_devices()

    assert result == [mock_device]
    mock_discovery.async_scan.assert_awaited_once()
