"""Tests for the moon sensor platform."""

from __future__ import annotations

from datetime import datetime
from math import degrees
from unittest.mock import patch

from astral import moon as astral_moon
import ephem
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.moon.const import PHASE_OPTIONS
from homeassistant.components.moon.coordinator import moon_phase_state
from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEGREE,
    PERCENTAGE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


def _to_datetime(value: ephem.Date) -> datetime:
    """Convert an ephem date to a UTC datetime."""
    return value.datetime().replace(tzinfo=dt_util.UTC)


def _entity_id(
    entity_registry: er.EntityRegistry,
    platform: str,
    unique_id: str,
) -> str:
    """Get an entity id by unique id."""
    entity_id = entity_registry.async_get_entity_id(platform, "moon", unique_id)
    assert entity_id is not None
    return entity_id


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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_moon_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Moon sensors."""
    utc_now = datetime(2026, 4, 10, 8, 0, 0, tzinfo=dt_util.UTC)
    freezer.move_to(utc_now)

    observer = ephem.Observer()
    observer.lat = str(hass.config.latitude)
    observer.lon = str(hass.config.longitude)
    observer.elevation = hass.config.elevation
    observer.date = utc_now
    current_moon = ephem.Moon(observer)

    expected_phase = moon_phase_state(astral_moon.phase(dt_util.now().date()))
    expected_next_rising = _to_datetime(observer.next_rising(ephem.Moon()))
    expected_next_setting = _to_datetime(observer.next_setting(ephem.Moon()))
    expected_next_new_moon = _to_datetime(ephem.next_new_moon(observer.date))
    expected_next_first_quarter_moon = _to_datetime(
        ephem.next_first_quarter_moon(observer.date)
    )
    expected_next_full_moon = _to_datetime(ephem.next_full_moon(observer.date))
    expected_next_last_quarter_moon = _to_datetime(
        ephem.next_last_quarter_moon(observer.date)
    )
    expected_next_transit = _to_datetime(observer.next_transit(ephem.Moon()))
    expected_elevation = degrees(float(current_moon.alt))
    expected_azimuth = degrees(float(current_moon.az))

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    next_first_quarter_moon_entity_id = _entity_id(
        entity_registry,
        "sensor",
        f"{mock_config_entry.entry_id}-next_first_quarter_moon",
    )
    next_last_quarter_moon_entity_id = _entity_id(
        entity_registry,
        "sensor",
        f"{mock_config_entry.entry_id}-next_last_quarter_moon",
    )

    phase_state = hass.states.get("sensor.moon_phase")
    assert phase_state
    assert phase_state.state == expected_phase
    assert phase_state.attributes[ATTR_FRIENDLY_NAME] == "Moon Phase"
    assert phase_state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert phase_state.attributes[ATTR_OPTIONS] == PHASE_OPTIONS

    illumination_state = hass.states.get("sensor.moon_illumination")
    assert illumination_state
    assert float(illumination_state.state) == pytest.approx(current_moon.phase, abs=0.1)
    assert illumination_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    next_rising_state = hass.states.get("sensor.moon_next_rising")
    assert next_rising_state
    assert expected_next_rising.replace(microsecond=0) == dt_util.parse_datetime(
        next_rising_state.state
    )

    next_setting_state = hass.states.get("sensor.moon_next_setting")
    assert next_setting_state
    assert expected_next_setting.replace(microsecond=0) == dt_util.parse_datetime(
        next_setting_state.state
    )

    next_new_moon_state = hass.states.get("sensor.moon_next_new_moon")
    assert next_new_moon_state
    assert expected_next_new_moon.replace(microsecond=0) == dt_util.parse_datetime(
        next_new_moon_state.state
    )

    next_first_quarter_moon_state = hass.states.get(next_first_quarter_moon_entity_id)
    assert next_first_quarter_moon_state
    assert expected_next_first_quarter_moon.replace(
        microsecond=0
    ) == dt_util.parse_datetime(next_first_quarter_moon_state.state)

    next_full_moon_state = hass.states.get("sensor.moon_next_full_moon")
    assert next_full_moon_state
    assert expected_next_full_moon.replace(microsecond=0) == dt_util.parse_datetime(
        next_full_moon_state.state
    )

    next_last_quarter_moon_state = hass.states.get(next_last_quarter_moon_entity_id)
    assert next_last_quarter_moon_state
    assert expected_next_last_quarter_moon.replace(
        microsecond=0
    ) == dt_util.parse_datetime(next_last_quarter_moon_state.state)

    next_transit_state = hass.states.get("sensor.moon_next_transit")
    assert next_transit_state
    assert expected_next_transit.replace(microsecond=0) == dt_util.parse_datetime(
        next_transit_state.state
    )

    elevation_state = hass.states.get("sensor.moon_elevation")
    assert elevation_state
    assert float(elevation_state.state) == pytest.approx(expected_elevation, abs=0.01)
    assert elevation_state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert elevation_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == DEGREE

    azimuth_state = hass.states.get("sensor.moon_azimuth")
    assert azimuth_state
    assert float(azimuth_state.state) == pytest.approx(expected_azimuth, abs=0.01)
    assert azimuth_state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert azimuth_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == DEGREE

    phase_entry = entity_registry.async_get("sensor.moon_phase")
    assert phase_entry
    assert phase_entry.unique_id == mock_config_entry.entry_id
    assert phase_entry.translation_key == "phase"

    illumination_entry = entity_registry.async_get("sensor.moon_illumination")
    assert illumination_entry
    assert illumination_entry.unique_id == f"{mock_config_entry.entry_id}-illumination"
    assert illumination_entry.translation_key == "illumination"
    assert illumination_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_rising_entry = entity_registry.async_get("sensor.moon_next_rising")
    assert next_rising_entry
    assert next_rising_entry.unique_id == f"{mock_config_entry.entry_id}-next_rising"
    assert next_rising_entry.translation_key == "next_rising"
    assert next_rising_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_setting_entry = entity_registry.async_get("sensor.moon_next_setting")
    assert next_setting_entry
    assert next_setting_entry.unique_id == f"{mock_config_entry.entry_id}-next_setting"
    assert next_setting_entry.translation_key == "next_setting"
    assert next_setting_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_new_moon_entry = entity_registry.async_get("sensor.moon_next_new_moon")
    assert next_new_moon_entry
    assert (
        next_new_moon_entry.unique_id == f"{mock_config_entry.entry_id}-next_new_moon"
    )
    assert next_new_moon_entry.translation_key == "next_new_moon"
    assert next_new_moon_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_first_quarter_moon_entry = entity_registry.async_get(
        next_first_quarter_moon_entity_id
    )
    assert next_first_quarter_moon_entry
    assert (
        next_first_quarter_moon_entry.unique_id
        == f"{mock_config_entry.entry_id}-next_first_quarter_moon"
    )
    assert next_first_quarter_moon_entry.translation_key == "next_first_quarter_moon"
    assert next_first_quarter_moon_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_full_moon_entry = entity_registry.async_get("sensor.moon_next_full_moon")
    assert next_full_moon_entry
    assert (
        next_full_moon_entry.unique_id == f"{mock_config_entry.entry_id}-next_full_moon"
    )
    assert next_full_moon_entry.translation_key == "next_full_moon"
    assert next_full_moon_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_last_quarter_moon_entry = entity_registry.async_get(
        next_last_quarter_moon_entity_id
    )
    assert next_last_quarter_moon_entry
    assert (
        next_last_quarter_moon_entry.unique_id
        == f"{mock_config_entry.entry_id}-next_last_quarter_moon"
    )
    assert next_last_quarter_moon_entry.translation_key == "next_last_quarter_moon"
    assert next_last_quarter_moon_entry.entity_category is EntityCategory.DIAGNOSTIC

    next_transit_entry = entity_registry.async_get("sensor.moon_next_transit")
    assert next_transit_entry
    assert next_transit_entry.unique_id == f"{mock_config_entry.entry_id}-next_transit"
    assert next_transit_entry.translation_key == "next_transit"
    assert next_transit_entry.entity_category is EntityCategory.DIAGNOSTIC

    elevation_entry = entity_registry.async_get("sensor.moon_elevation")
    assert elevation_entry
    assert elevation_entry.unique_id == f"{mock_config_entry.entry_id}-elevation"
    assert elevation_entry.translation_key == "elevation"
    assert elevation_entry.entity_category is EntityCategory.DIAGNOSTIC

    azimuth_entry = entity_registry.async_get("sensor.moon_azimuth")
    assert azimuth_entry
    assert azimuth_entry.unique_id == f"{mock_config_entry.entry_id}-azimuth"
    assert azimuth_entry.translation_key == "azimuth"
    assert azimuth_entry.entity_category is EntityCategory.DIAGNOSTIC

    assert phase_entry.device_id
    device_entry = device_registry.async_get(phase_entry.device_id)
    assert device_entry
    assert device_entry.name == "Moon"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE


async def test_moon_disabled_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test azimuth and elevation sensors are disabled by default."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.moon_elevation") is None
    assert hass.states.get("sensor.moon_azimuth") is None

    elevation_entry = entity_registry.async_get("sensor.moon_elevation")
    assert elevation_entry
    assert elevation_entry.disabled

    azimuth_entry = entity_registry.async_get("sensor.moon_azimuth")
    assert azimuth_entry
    assert azimuth_entry.disabled


async def test_moon_rising_setting_error_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rising and setting sensors become unknown on observer errors."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.moon.coordinator.ephem.Observer.next_rising",
            side_effect=ephem.AlwaysUpError,
        ),
        patch(
            "homeassistant.components.moon.coordinator.ephem.Observer.next_setting",
            side_effect=ephem.NeverUpError,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    next_rising_state = hass.states.get("sensor.moon_next_rising")
    assert next_rising_state
    assert next_rising_state.state == STATE_UNKNOWN

    next_setting_state = hass.states.get("sensor.moon_next_setting")
    assert next_setting_state
    assert next_setting_state.state == STATE_UNKNOWN
