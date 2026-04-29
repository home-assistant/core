"""Tests for the moon sensor platform."""

from __future__ import annotations

from unittest.mock import patch

import ephem
import pytest

from homeassistant.components.moon.const import (
    PHASE_OPTIONS,
    STATE_FIRST_QUARTER,
    STATE_FULL_MOON,
    STATE_LAST_QUARTER,
    STATE_NEW_MOON,
    STATE_WANING_CRESCENT,
    STATE_WANING_GIBBOUS,
    STATE_WAXING_CRESCENT,
    STATE_WAXING_GIBBOUS,
)
from homeassistant.components.moon.coordinator import _get_next_event, moon_phase_state
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
def test_moon_phase_state(moon_value: float, native_value: str) -> None:
    """Test moon phase mapping."""
    assert moon_phase_state(moon_value) == native_value


@pytest.mark.parametrize(
    ("moon_value", "native_value"),
    [
        (0.4, STATE_NEW_MOON),
        (0.5, STATE_WAXING_CRESCENT),
        (6.49, STATE_WAXING_CRESCENT),
        (6.5, STATE_FIRST_QUARTER),
        (7.49, STATE_FIRST_QUARTER),
        (7.5, STATE_WAXING_GIBBOUS),
        (13.49, STATE_WAXING_GIBBOUS),
        (13.5, STATE_FULL_MOON),
        (14.49, STATE_FULL_MOON),
        (14.5, STATE_WANING_GIBBOUS),
        (20.49, STATE_WANING_GIBBOUS),
        (20.5, STATE_LAST_QUARTER),
        (21.49, STATE_LAST_QUARTER),
        (21.5, STATE_WANING_CRESCENT),
        (27.5, STATE_WANING_CRESCENT),
        (27.51, STATE_NEW_MOON),
    ],
)
async def test_moon_phase_sensor_boundary_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    moon_value: float,
    native_value: str,
) -> None:
    """Test phase sensor boundary mapping against the integration."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.moon.coordinator.astral_moon.phase",
        return_value=moon_value,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.moon_phase")
    assert state
    assert state.state == native_value


@pytest.mark.parametrize("error", [ephem.AlwaysUpError, ephem.NeverUpError])
def test_get_next_event_returns_none_on_ephem_error(
    error: type[ephem.AlwaysUpError | ephem.NeverUpError],
) -> None:
    """Test next moon event calculation handles missing events."""

    def raise_error(_moon: ephem.Moon) -> ephem.Date:
        raise error

    assert _get_next_event(ephem.Moon(), raise_error) is None


async def test_moon_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Moon sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.moon_phase")
    assert state
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Moon Phase"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == PHASE_OPTIONS

    entry = entity_registry.async_get("sensor.moon_phase")
    assert entry
    assert entry.unique_id == mock_config_entry.entry_id
    assert entry.translation_key == "phase"

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Moon"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
