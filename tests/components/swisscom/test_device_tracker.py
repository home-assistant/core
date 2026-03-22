"""Tests for the Swisscom device tracker."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.swisscom.device_tracker import (
    SwisscomDeviceTracker,
    async_setup_platform,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed

MOCK_DATA = {
    "device1": {
        "ip": "192.168.1.10",
        "mac": "AA:BB:CC:DD:EE:FF",
        "host": "Device1",
        "status": True,
    },
    "device2": {
        "ip": "192.168.1.11",
        "mac": "11:22:33:44:55:66",
        "host": "Device2",
        "status": True,
    },
}


def _collect_entities() -> tuple[list[SwisscomDeviceTracker], Any]:
    """Create an entity collector and callback."""
    entities: list[SwisscomDeviceTracker] = []

    def add_entities(
        new_entities: list[SwisscomDeviceTracker],
        update_before_add: bool = False,
    ) -> None:
        entities.extend(new_entities)

    return entities, add_entities


@pytest.fixture
def mock_get_data() -> MagicMock:
    """Mock _get_swisscom_data."""
    with patch(
        "homeassistant.components.swisscom.device_tracker._get_swisscom_data",
        return_value=dict(MOCK_DATA),
    ) as mock_fn:
        yield mock_fn


async def test_setup_platform(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
) -> None:
    """Test successful platform setup creates entities."""
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.1"}, add_entities)

    assert len(entities) == 2
    macs = {e.mac_address for e in entities}
    assert "AA:BB:CC:DD:EE:FF" in macs
    assert "11:22:33:44:55:66" in macs
    for entity in entities:
        assert entity.is_connected is True


async def test_setup_platform_connection_failure(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
) -> None:
    """Test platform setup when router is unreachable."""
    mock_get_data.return_value = None
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.1"}, add_entities)

    assert len(entities) == 0


async def test_setup_platform_no_active_devices(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
) -> None:
    """Test platform setup when no devices are active."""
    mock_get_data.return_value = {
        "device1": {
            "ip": "192.168.1.10",
            "mac": "AA:BB:CC:DD:EE:FF",
            "host": "Device1",
            "status": False,
        },
    }
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.1"}, add_entities)

    assert len(entities) == 0


async def test_device_becomes_disconnected(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
) -> None:
    """Test device shows disconnected when absent from scan."""
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.1"}, add_entities)

    assert len(entities) == 2
    assert entities[0].is_connected is True
    assert entities[1].is_connected is True

    # Next scan returns only the first device as active
    mock_get_data.return_value = {
        "device1": {
            "ip": "192.168.1.10",
            "mac": "AA:BB:CC:DD:EE:FF",
            "host": "Device1",
            "status": True,
        },
    }
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # Find entities by mac
    entity_ff = next(e for e in entities if e.mac_address == "AA:BB:CC:DD:EE:FF")
    entity_66 = next(e for e in entities if e.mac_address == "11:22:33:44:55:66")
    assert entity_ff.is_connected is True
    assert entity_66.is_connected is False


async def test_new_device_discovered(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
) -> None:
    """Test new devices are discovered on subsequent scans."""
    mock_get_data.return_value = {
        "device1": {
            "ip": "192.168.1.10",
            "mac": "AA:BB:CC:DD:EE:FF",
            "host": "Device1",
            "status": True,
        },
    }
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.1"}, add_entities)

    assert len(entities) == 1

    # Second device appears on next scan
    mock_get_data.return_value = dict(MOCK_DATA)
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    assert len(entities) == 2
    assert entities[1].mac_address == "11:22:33:44:55:66"
    assert entities[1].is_connected is True


async def test_entity_hostname_updates(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
) -> None:
    """Test hostname reflects latest scan data."""
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.1"}, add_entities)

    entity = next(e for e in entities if e.mac_address == "AA:BB:CC:DD:EE:FF")
    assert entity.hostname == "Device1"

    # Device name changes on next scan
    mock_get_data.return_value = {
        "device1": {
            "ip": "192.168.1.10",
            "mac": "AA:BB:CC:DD:EE:FF",
            "host": "NewName",
            "status": True,
        },
    }
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    assert entity.hostname == "NewName"


async def test_scan_with_no_data_preserves_state(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
) -> None:
    """Test that a failed scan preserves existing state."""
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.1"}, add_entities)

    assert len(entities) == 2
    assert entities[0].is_connected is True

    # Next scan fails
    mock_get_data.return_value = None
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    # State preserved from last successful scan
    assert entities[0].is_connected is True
    assert len(entities) == 2


async def test_empty_data_returns_no_entities(
    hass: HomeAssistant,
    mock_get_data: MagicMock,
) -> None:
    """Test empty data dict returns no entities."""
    mock_get_data.return_value = {}
    entities, add_entities = _collect_entities()

    await async_setup_platform(hass, {CONF_HOST: "192.168.1.1"}, add_entities)

    assert len(entities) == 0
