"""Tests for Honeywell Lyric leak detector sensors."""

from unittest.mock import patch

import pytest

from homeassistant.components.lyric.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import L1_ID, WLD3_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_lyric")
async def test_leak_detector_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WLD3 and L1 leak detector sensors."""
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{WLD3_ID}_signal_strength",
        suggested_object_id="laundry_signal_strength",
    )

    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    expected_sensors = {
        "temperature": (
            "20.85",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
        ),
        "humidity": ("57.7", SensorDeviceClass.HUMIDITY, PERCENTAGE),
        "battery": ("29", SensorDeviceClass.BATTERY, PERCENTAGE),
    }
    for key, (expected_state, device_class, unit) in expected_sensors.items():
        entity_id = entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{WLD3_ID}_{key}"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state
        assert state.attributes[ATTR_DEVICE_CLASS] == device_class
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit

    signal_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{WLD3_ID}_signal_strength"
    )
    assert signal_entity_id is not None
    signal_state = hass.states.get(signal_entity_id)
    assert signal_state is not None
    assert signal_state.state == "-48"
    assert (
        signal_state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SIGNAL_STRENGTH
    )
    assert (
        signal_state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )

    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{L1_ID}_signal_strength"
        )
        is None
    )

    l1_battery_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{L1_ID}_battery"
    )
    assert l1_battery_entity_id is not None
    l1_battery_state = hass.states.get(l1_battery_entity_id)
    assert l1_battery_state is not None
    assert l1_battery_state.state == "100"
    assert l1_battery_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
