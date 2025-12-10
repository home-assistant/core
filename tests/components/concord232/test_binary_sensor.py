"""Tests for the Concord232 binary sensor platform."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
import requests

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.concord232.binary_sensor import (
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed

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
    hass: HomeAssistant, mock_concord232_client: MagicMock
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
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test platform setup with connection error."""
    mock_concord232_client.list_zones.side_effect = requests.exceptions.ConnectionError(
        "Connection failed"
    )

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    assert "Unable to connect to Concord232" in caplog.text
    assert hass.states.get("binary_sensor.zone_1") is None


async def test_setup_with_exclude_zones(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test platform setup with excluded zones."""
    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG_WITH_EXCLUDE)
    await hass.async_block_till_done()

    state1 = hass.states.get("binary_sensor.zone_1")
    state2 = hass.states.get("binary_sensor.zone_2")
    assert state1 is not None
    assert state2 is None  # Zone 2 should be excluded


async def test_setup_with_zone_types(
    hass: HomeAssistant, mock_concord232_client: MagicMock
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
    assert state1.attributes.get("device_class") == BinarySensorDeviceClass.DOOR
    assert state2.attributes.get("device_class") == BinarySensorDeviceClass.WINDOW


async def test_zone_state_faulted(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test zone state when faulted."""
    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Faulted"},
    ]
    mock_concord232_client.zones = mock_concord232_client.list_zones.return_value

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.zone_1")
    assert state.state == "on"  # Faulted state means on (faulted)


@pytest.mark.freeze_time("2023-10-21")
async def test_zone_update_refresh(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that zone updates refresh the client data."""
    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": "Zone 1", "state": "Normal"},
    ]
    mock_concord232_client.zones = mock_concord232_client.list_zones.return_value

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.zone_1").state == "off"

    # Update zone state - need to update both return_value and zones attribute
    new_zones = [
        {"number": 1, "name": "Zone 1", "state": "Faulted"},
    ]
    mock_concord232_client.list_zones.return_value = new_zones
    mock_concord232_client.zones = new_zones

    freezer.tick(datetime.timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(datetime.timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.zone_1")
    assert state.state == "on"


@pytest.mark.parametrize(
    ("sensor_name", "entity_id", "expected_device_class"),
    [
        (
            "MOTION Sensor",
            "binary_sensor.motion_sensor",
            BinarySensorDeviceClass.MOTION,
        ),
        ("SMOKE Sensor", "binary_sensor.smoke_sensor", BinarySensorDeviceClass.SMOKE),
        (
            "Unknown Sensor",
            "binary_sensor.unknown_sensor",
            BinarySensorDeviceClass.OPENING,
        ),
    ],
)
async def test_device_class(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    sensor_name: str,
    entity_id: str,
    expected_device_class: BinarySensorDeviceClass,
) -> None:
    """Test zone type detection for motion sensor."""
    mock_concord232_client.list_zones.return_value = [
        {"number": 1, "name": sensor_name, "state": "Normal"},
    ]
    mock_concord232_client.zones = mock_concord232_client.list_zones.return_value

    await async_setup_component(hass, BINARY_SENSOR_DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes.get("device_class") == expected_device_class
