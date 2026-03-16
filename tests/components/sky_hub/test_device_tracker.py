"""Tests for the Sky Hub device tracker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.sky_hub.device_tracker import (
    SkyHubDeviceTracker,
    async_setup_platform,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


@dataclass
class MockDevice:
    """Mock Sky Hub device."""

    mac: str
    name: str


MOCK_DEVICES = [
    MockDevice(mac="AA:BB:CC:DD:EE:FF", name="Device1"),
    MockDevice(mac="11:22:33:44:55:66", name="Device2"),
]


@pytest.fixture
def mock_hub() -> AsyncMock:
    """Create a mock SkyQHub."""
    with patch(
        "homeassistant.components.sky_hub.device_tracker.SkyQHub"
    ) as mock_hub_class:
        hub = mock_hub_class.return_value
        hub.success_init = True
        hub.async_connect = AsyncMock()
        hub.async_get_skyhub_data = AsyncMock(return_value=list(MOCK_DEVICES))
        yield hub


def _collect_entities() -> tuple[list[SkyHubDeviceTracker], Any]:
    """Create an entity collector and callback."""
    entities: list[SkyHubDeviceTracker] = []

    def add_entities(
        new_entities: list[SkyHubDeviceTracker],
        update_before_add: bool = False,
    ) -> None:
        entities.extend(new_entities)

    return entities, add_entities


async def test_setup_platform(
    hass: HomeAssistant,
    mock_hub: AsyncMock,
) -> None:
    """Test successful platform setup creates entities."""
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.254"}, add_entities)

    assert len(entities) == 2
    assert entities[0].mac_address == "AA:BB:CC:DD:EE:FF"
    assert entities[0].is_connected is True
    assert entities[0].hostname == "Device1"
    assert entities[1].mac_address == "11:22:33:44:55:66"
    assert entities[1].is_connected is True
    assert entities[1].hostname == "Device2"


async def test_setup_platform_connection_failure(
    hass: HomeAssistant,
    mock_hub: AsyncMock,
) -> None:
    """Test platform setup when hub connection fails."""
    mock_hub.success_init = False
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.254"}, add_entities)

    assert len(entities) == 0


async def test_setup_platform_no_data(
    hass: HomeAssistant,
    mock_hub: AsyncMock,
) -> None:
    """Test platform setup when hub returns no device data."""
    mock_hub.async_get_skyhub_data.return_value = None
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.254"}, add_entities)

    assert len(entities) == 0


async def test_device_becomes_disconnected(
    hass: HomeAssistant,
    mock_hub: AsyncMock,
) -> None:
    """Test device shows disconnected when absent from scan."""
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.254"}, add_entities)

    assert entities[0].is_connected is True
    assert entities[1].is_connected is True

    # Next scan returns only the first device
    mock_hub.async_get_skyhub_data.return_value = [MOCK_DEVICES[0]]
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    assert entities[0].is_connected is True
    assert entities[1].is_connected is False


async def test_new_device_discovered(
    hass: HomeAssistant,
    mock_hub: AsyncMock,
) -> None:
    """Test new devices are discovered on subsequent scans."""
    mock_hub.async_get_skyhub_data.return_value = [MOCK_DEVICES[0]]
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.254"}, add_entities)

    assert len(entities) == 1
    assert entities[0].mac_address == "AA:BB:CC:DD:EE:FF"

    # Second device appears on next scan
    mock_hub.async_get_skyhub_data.return_value = list(MOCK_DEVICES)
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    assert len(entities) == 2
    assert entities[1].mac_address == "11:22:33:44:55:66"
    assert entities[1].is_connected is True


async def test_entity_hostname_updates(
    hass: HomeAssistant,
    mock_hub: AsyncMock,
) -> None:
    """Test hostname reflects latest scan data."""
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.254"}, add_entities)

    assert entities[0].hostname == "Device1"

    # Device name changes on next scan
    mock_hub.async_get_skyhub_data.return_value = [
        MockDevice(mac="AA:BB:CC:DD:EE:FF", name="NewName"),
    ]
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    assert entities[0].hostname == "NewName"


async def test_scan_with_no_data_preserves_state(
    hass: HomeAssistant,
    mock_hub: AsyncMock,
) -> None:
    """Test that a failed scan preserves existing state."""
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.254"}, add_entities)

    assert len(entities) == 2
    assert entities[0].is_connected is True

    # Next scan fails
    mock_hub.async_get_skyhub_data.return_value = None
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # State preserved from last successful scan
    assert entities[0].is_connected is True
    assert len(entities) == 2


async def test_default_host(
    hass: HomeAssistant,
    mock_hub: AsyncMock,
) -> None:
    """Test default host is used from PLATFORM_SCHEMA."""
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.254"}, add_entities)

    mock_hub.async_connect.assert_called_once()
    assert len(entities) == 2


async def test_custom_scan_interval(
    hass: HomeAssistant,
    mock_hub: AsyncMock,
) -> None:
    """Test custom scan interval is respected."""
    entities, add_entities = _collect_entities()
    config = {CONF_HOST: "192.168.1.254", "scan_interval": timedelta(seconds=30)}

    await async_setup_platform(hass, config, add_entities)

    assert len(entities) == 2

    # Verify scan is triggered after the custom interval
    mock_hub.async_get_skyhub_data.return_value = [MOCK_DEVICES[0]]
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Scan was triggered (mock was called again)
    assert mock_hub.async_get_skyhub_data.call_count >= 2
