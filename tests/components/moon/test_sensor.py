"""The test for the moon sensor platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.moon.sensor import (
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)
from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("moon_value", "native_value"),
    [
        (0, STATE_NEW_MOON),
        (5, STATE_WAXING_CRESCENT),
        (7, STATE_FIRST_QUARTER),
        (12, STATE_WAXING_GIBBOUS),
        (14.3, STATE_FULL_MOON),
        (20.1, STATE_WANING_GIBBOUS),
        (20.8, STATE_LAST_QUARTER),
        (23, STATE_WANING_CRESCENT),
    ],
)
async def test_moon_day(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    moon_value: float,
    native_value: str,
) -> None:
    """Test the Moon sensor."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.moon.sensor.moon.phase", return_value=moon_value
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.moon_phase")
    assert state
    assert state.state == native_value
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Moon Phase"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == [
        STATE_NEW_MOON,
        STATE_WAXING_CRESCENT,
        STATE_FIRST_QUARTER,
        STATE_WAXING_GIBBOUS,
        STATE_FULL_MOON,
        STATE_WANING_GIBBOUS,
        STATE_LAST_QUARTER,
        STATE_WANING_CRESCENT,
    ]

    entry = entity_registry.async_get("sensor.moon_phase")
    assert entry
    assert entry.unique_id == mock_config_entry.entry_id
    assert entry.translation_key == "phase"

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Moon"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
