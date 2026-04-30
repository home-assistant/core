"""Tests for the moon sensor platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.moon.const import PHASE_OPTIONS
from homeassistant.components.moon.coordinator import moon_phase_state
from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("moon_value", "native_value"),
    [
        (0, "new_moon"),
        (5, "waxing_crescent"),
        (7, "first_quarter"),
        (12, "waxing_gibbous"),
        (14.3, "full_moon"),
        (20.1, "waning_gibbous"),
        (20.8, "last_quarter"),
        (23, "waning_crescent"),
    ],
)
def test_moon_phase_state(moon_value: float, native_value: str) -> None:
    """Test moon phase mapping."""
    assert moon_phase_state(moon_value) == native_value


@pytest.mark.parametrize(
    ("moon_value", "native_value"),
    [
        (0.4, "new_moon"),
        (0.5, "waxing_crescent"),
        (6.49, "waxing_crescent"),
        (6.5, "first_quarter"),
        (7.49, "first_quarter"),
        (7.5, "waxing_gibbous"),
        (13.49, "waxing_gibbous"),
        (13.5, "full_moon"),
        (14.49, "full_moon"),
        (14.5, "waning_gibbous"),
        (20.49, "waning_gibbous"),
        (20.5, "last_quarter"),
        (21.49, "last_quarter"),
        (21.5, "waning_crescent"),
        (27.5, "waning_crescent"),
        (27.51, "new_moon"),
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
