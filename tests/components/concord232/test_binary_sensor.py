"""Tests for the Concord232 binary sensor platform."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
import requests

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.concord232 import binary_sensor
from homeassistant.const import CONF_HOST, CONF_PORT

CONF_EXCLUDE_ZONES = "exclude_zones"
CONF_ZONE_TYPES = "zone_types"
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

VALID_CONFIG = {
    BINARY_SENSOR_DOMAIN: {
        "platform": "concord232",
        CONF_HOST: "localhost",
        CONF_PORT: 5007,
    }
}

VALID_CONFIG_WITH_EXCLUDE = {
    BINARY_SENSOR_DOMAIN: {
        "platform": "concord232",
        CONF_HOST: "localhost",
        CONF_PORT: 5007,
        CONF_EXCLUDE_ZONES: [2],
    }
}

VALID_CONFIG_WITH_ZONE_TYPES = {
    BINARY_SENSOR_DOMAIN: {
        "platform": "concord232",
        CONF_HOST: "localhost",
        CONF_PORT: 5007,
        CONF_ZONE_TYPES: {1: "door", 2: "window"},
    }
}


async def test_setup_platform(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test platform setup."""
    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state1 = hass.states.get("binary_sensor.zone_1")
    state2 = hass.states.get("binary_sensor.zone_2")
    assert state1 is not None
    assert state2 is not None
    assert state1.state == "off"
    assert state2.state == "off"


async def test_setup_platform_connection_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test platform setup with connection error."""
    with patch(
        "homeassistant.components.concord232.binary_sensor.concord232_client.Client"
    ) as mock_client_class:
        mock_client_class.side_effect = requests.exceptions.ConnectionError(
            "Connection failed"
        )

        await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
        await hass.async_block_till_done()

        assert "Unable to connect to Concord232" in caplog.text
        assert hass.states.get("binary_sensor.zone_1") is None


async def test_setup_with_exclude_zones(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test platform setup with excluded zones."""
    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG_WITH_EXCLUDE)
    await hass.async_block_till_done()

    state1 = hass.states.get("binary_sensor.zone_1")
    state2 = hass.states.get("binary_sensor.zone_2")
    assert state1 is not None
    assert state2 is None  # Zone 2 should be excluded


async def test_setup_with_zone_types(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test platform setup with custom zone types."""
    await async_setup_component(
        hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG_WITH_ZONE_TYPES
    )
    await hass.async_block_till_done()

    state1 = hass.states.get("binary_sensor.zone_1")
    state2 = hass.states.get("binary_sensor.zone_2")
    assert state1 is not None
    assert state2 is not None
    # Check device class is set correctly
    assert state1.attributes.get("device_class") == "door"
    assert state2.attributes.get("device_class") == "window"


async def test_zone_state_normal(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test zone state when normal."""
    mock_concord232_binary_sensor_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Normal"},
    ]
    mock_concord232_binary_sensor_client.zones = (
        mock_concord232_binary_sensor_client.list_zones.return_value
    )

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.zone_1")
    assert state.state == "off"  # Normal state means off (not faulted)


async def test_zone_state_faulted(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test zone state when faulted."""
    mock_concord232_binary_sensor_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Faulted"},
    ]
    mock_concord232_binary_sensor_client.zones = (
        mock_concord232_binary_sensor_client.list_zones.return_value
    )

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Trigger update
    await async_update_entity(hass, "binary_sensor.zone_1")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.zone_1")
    assert state.state == "on"  # Faulted state means on (faulted)


async def test_zone_update_refresh(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test that zone updates refresh the client data."""
    mock_concord232_binary_sensor_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Normal"},
    ]
    mock_concord232_binary_sensor_client.zones = (
        mock_concord232_binary_sensor_client.list_zones.return_value
    )

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Update zone state - need to update both return_value and zones attribute
    new_zones = [
        {"number": 1, "name": "Zone 1", "state": "Faulted"},
    ]
    mock_concord232_binary_sensor_client.list_zones.return_value = new_zones
    mock_concord232_binary_sensor_client.zones = new_zones

    # Trigger update - need to wait a bit for the time check to pass
    await asyncio.sleep(0.1)
    await async_update_entity(hass, "binary_sensor.zone_1")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.zone_1")
    assert state.state == "on"


async def test_get_opening_type_motion(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test zone type detection for motion sensor."""
    mock_concord232_binary_sensor_client.list_zones.return_value = [
        {"number": 1, "name": "MOTION Sensor", "state": "Normal"},
    ]
    mock_concord232_binary_sensor_client.zones = (
        mock_concord232_binary_sensor_client.list_zones.return_value
    )

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.motion_sensor")
    assert state.attributes.get("device_class") == "motion"


async def test_get_opening_type_smoke(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test zone type detection for smoke sensor."""
    mock_concord232_binary_sensor_client.list_zones.return_value = [
        {"number": 1, "name": "SMOKE Sensor", "state": "Normal"},
    ]
    mock_concord232_binary_sensor_client.zones = (
        mock_concord232_binary_sensor_client.list_zones.return_value
    )

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.smoke_sensor")
    assert state.attributes.get("device_class") == "smoke"


async def test_get_opening_type_default(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test zone type defaults to opening when no match."""
    mock_concord232_binary_sensor_client.list_zones.return_value = [
        {"number": 1, "name": "Unknown Sensor", "state": "Normal"},
    ]
    mock_concord232_binary_sensor_client.zones = (
        mock_concord232_binary_sensor_client.list_zones.return_value
    )

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.unknown_sensor")
    assert state.attributes.get("device_class") == "opening"


async def test_zones_sorted_by_number(
    hass: HomeAssistant, mock_concord232_binary_sensor_client: MagicMock
) -> None:
    """Test that zones are sorted by number."""
    # Return zones in non-sorted order
    mock_concord232_binary_sensor_client.list_zones.return_value = [
        {"number": 3, "name": "Zone 3", "state": "Normal"},
        {"number": 1, "name": "Zone 1", "state": "Normal"},
        {"number": 2, "name": "Zone 2", "state": "Normal"},
    ]
    mock_concord232_binary_sensor_client.zones = (
        mock_concord232_binary_sensor_client.list_zones.return_value
    )

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    # Verify zones are sorted
    assert mock_concord232_binary_sensor_client.zones[0]["number"] == 1
    assert mock_concord232_binary_sensor_client.zones[1]["number"] == 2
    assert mock_concord232_binary_sensor_client.zones[2]["number"] == 3
