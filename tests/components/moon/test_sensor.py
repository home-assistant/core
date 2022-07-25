"""The test for the moon sensor platform."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.moon.sensor import (
    MOON_ICONS,
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "moon_value,native_value,icon",
    [
        (0, STATE_NEW_MOON, MOON_ICONS[STATE_NEW_MOON]),
        (5, STATE_WAXING_CRESCENT, MOON_ICONS[STATE_WAXING_CRESCENT]),
        (7, STATE_FIRST_QUARTER, MOON_ICONS[STATE_FIRST_QUARTER]),
        (12, STATE_WAXING_GIBBOUS, MOON_ICONS[STATE_WAXING_GIBBOUS]),
        (14.3, STATE_FULL_MOON, MOON_ICONS[STATE_FULL_MOON]),
        (20.1, STATE_WANING_GIBBOUS, MOON_ICONS[STATE_WANING_GIBBOUS]),
        (20.8, STATE_LAST_QUARTER, MOON_ICONS[STATE_LAST_QUARTER]),
        (23, STATE_WANING_CRESCENT, MOON_ICONS[STATE_WANING_CRESCENT]),
    ],
)
async def test_moon_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    moon_value: float,
    native_value: str,
    icon: str,
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
    assert state.attributes[ATTR_ICON] == icon
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Moon Phase"

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.moon_phase")
    assert entry
    assert entry.unique_id == mock_config_entry.entry_id

    device_registry = dr.async_get(hass)
    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Moon"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
