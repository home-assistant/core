"""Tests for the UniFi Access discovery module."""

from __future__ import annotations

from unittest.mock import patch

from unifi_discovery import UnifiDevice, UnifiService

from homeassistant.components.unifi_access.discovery import (
    async_start_discovery,
    async_trigger_discovery,
)
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.core import HomeAssistant

from .conftest import MOCK_HOST


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


async def test_trigger_discovery_creates_flow(hass: HomeAssistant) -> None:
    """Test that discovered Access devices trigger config flows."""
    device = _make_device()
    with patch(
        "homeassistant.components.unifi_access.discovery.discovery_flow.async_create_flow"
    ) as mock_create:
        async_trigger_discovery(hass, [device])

    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args
    assert call_kwargs[1]["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY


async def test_trigger_discovery_skips_non_access(hass: HomeAssistant) -> None:
    """Test that devices without Access service are skipped."""
    device = _make_device(access=False)
    with patch(
        "homeassistant.components.unifi_access.discovery.discovery_flow.async_create_flow"
    ) as mock_create:
        async_trigger_discovery(hass, [device])

    mock_create.assert_not_called()


async def test_trigger_discovery_skips_no_mac(hass: HomeAssistant) -> None:
    """Test that devices without hw_addr are skipped."""
    device = _make_device(hw_addr="")
    with patch(
        "homeassistant.components.unifi_access.discovery.discovery_flow.async_create_flow"
    ) as mock_create:
        async_trigger_discovery(hass, [device])

    mock_create.assert_not_called()


async def test_start_discovery_only_starts_once(hass: HomeAssistant) -> None:
    """Test that discovery is started only once."""
    with patch(
        "homeassistant.components.unifi_access.discovery.async_discover_devices",
        return_value=[],
    ) as mock_discover:
        async_start_discovery(hass)
        async_start_discovery(hass)
        await hass.async_block_till_done()

    mock_discover.assert_called_once()
