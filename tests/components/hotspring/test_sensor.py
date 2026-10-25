"""Tests for the Hot Spring sensor platform."""

import math
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from hotspring import FreshWaterIQ, HotSpringConnectionError, Spa, TemperatureUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hotspring.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

ENTITY_IDS: tuple[tuple[str, str], ...] = (
    ("sensor.connectedspa_ddeeff_ph", "7.7"),
    ("sensor.connectedspa_ddeeff_chlorine", "23.1"),
    ("sensor.connectedspa_ddeeff_oxidation_reduction_potential", "793"),
    ("sensor.connectedspa_ddeeff_sensor_life", "79.06"),
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor platform state."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_temperature_sensor_celsius(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the temperature sensor when the spa is configured in Celsius."""
    device_fixture.heater.temperature_unit = TemperatureUnit.CELSIUS
    device_fixture.heater.current_temperature = 38.5
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.connectedspa_ddeeff_current_temperature") == snapshot


def _enable_freshwater_iq(device_fixture: Spa) -> None:
    """Configure the spa fixture with installed FreshWater IQ sensors."""
    device_fixture.freshwater_iq.installed = True
    device_fixture.freshwater_iq.ph = 7.7
    device_fixture.freshwater_iq.chlorine = 23.1
    device_fixture.freshwater_iq.orp = 793
    device_fixture.freshwater_iq.sensor_life_percentage = 79.06


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_freshwater_iq_sensors_installed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the FreshWater IQ sensors when the IQ system is installed."""
    _enable_freshwater_iq(device_fixture)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    for entity_id, expected_state in ENTITY_IDS:
        assert hass.states.get(entity_id).state == expected_state


async def test_freshwater_iq_sensors_absent_without_iq(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test that no FreshWater IQ sensors are created when IQ is not installed."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    for entity_id, _ in ENTITY_IDS:
        assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_freshwater_iq_sensors_discovered_after_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test FreshWater IQ sensors appear with stable unique ids when discovered later."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    for entity_id, _ in ENTITY_IDS:
        assert hass.states.get(entity_id) is None

    _enable_freshwater_iq(device_fixture)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    unique_ids = {
        f"AA:BB:CC:DD:EE:FF_{key}"
        for key in (
            "freshwater_iq_ph",
            "freshwater_iq_chlorine",
            "freshwater_iq_orp",
            "freshwater_iq_sensor_life",
        )
    }
    registered = {
        entry.unique_id
        for entry in entity_registry.entities.values()
        if entry.config_entry_id == mock_config_entry.entry_id
        and entry.unique_id.startswith("AA:BB:CC:DD:EE:FF_freshwater_iq")
    }
    assert registered == unique_ids

    for entity_id, expected_state in ENTITY_IDS:
        assert hass.states.get(entity_id).state == expected_state

    # A further refresh must not create duplicate entities.
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    registered_again = {
        entry.unique_id
        for entry in entity_registry.entities.values()
        if entry.config_entry_id == mock_config_entry.entry_id
        and entry.unique_id.startswith("AA:BB:CC:DD:EE:FF_freshwater_iq")
    }
    assert registered_again == unique_ids
    for entity_id, expected_state in ENTITY_IDS:
        assert hass.states.get(entity_id).state == expected_state


@pytest.mark.parametrize(
    ("attribute", "value", "expected_state"),
    [
        pytest.param("ph", 0.0, "0.0", id="valid_zero_ph"),
        pytest.param("chlorine", 0.0, "0.0", id="valid_zero_chlorine"),
        pytest.param("sensor_life_percentage", 0.0, "0.0", id="valid_zero_sensor_life"),
        pytest.param("ph", -1.0, STATE_UNKNOWN, id="sentinel_ph"),
        pytest.param("chlorine", -1.0, STATE_UNKNOWN, id="sentinel_chlorine"),
        pytest.param("orp", -1, STATE_UNKNOWN, id="sentinel_orp"),
        pytest.param(
            "sensor_life_percentage", -1.0, STATE_UNKNOWN, id="sentinel_sensor_life"
        ),
        pytest.param("ph", math.nan, STATE_UNKNOWN, id="nonfinite_nan_ph"),
        pytest.param("chlorine", math.inf, STATE_UNKNOWN, id="nonfinite_inf_chlorine"),
        pytest.param("orp", -59, "-59", id="negative_orp_preserved"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_freshwater_iq_reading_validity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    attribute: str,
    value: float,
    expected_state: str,
) -> None:
    """Test valid zero readings are kept and sentinels and non-finite values are unknown."""
    _enable_freshwater_iq(device_fixture)
    setattr(device_fixture.freshwater_iq, attribute, value)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    entity_ids = {
        "ph": "sensor.connectedspa_ddeeff_ph",
        "chlorine": "sensor.connectedspa_ddeeff_chlorine",
        "orp": "sensor.connectedspa_ddeeff_oxidation_reduction_potential",
        "sensor_life_percentage": "sensor.connectedspa_ddeeff_sensor_life",
    }
    assert hass.states.get(entity_ids[attribute]).state == expected_state


async def test_freshwater_iq_fields_omitted_from_poll_retain_previous(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    mock_hotspring: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that /status polls omitting IQ fields keep the previous values, like temperature."""
    _enable_freshwater_iq(device_fixture)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.connectedspa_ddeeff_chlorine").state == "23.1"

    # Simulate the next /status poll omitting the chlorine and pH fields; the
    # library merge retains their previous values at this parser boundary.
    device_fixture.freshwater_iq = FreshWaterIQ.from_dict(
        {
            "current_ORP": 800,
            "current_SensorLife_Percentage": 78.0,
        },
        existing=device_fixture.freshwater_iq,
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.connectedspa_ddeeff_chlorine").state == "23.1"
    assert hass.states.get("sensor.connectedspa_ddeeff_ph").state == "7.7"
    assert (
        hass.states.get(
            "sensor.connectedspa_ddeeff_oxidation_reduction_potential"
        ).state
        == "800"
    )
    assert hass.states.get("sensor.connectedspa_ddeeff_sensor_life").state == "78.0"


async def test_freshwater_iq_field_absent_on_first_observation_reports_library_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    mock_hotspring: MagicMock,
) -> None:
    """Test the accepted library behavior for a field absent on first observation.

    python-hotspring does not record which fields were present the first time
    the FreshWater IQ is identified as installed; a field absent on that first
    poll keeps the library default (0) until the spa first reports it.
    """
    device_fixture.freshwater_iq = FreshWaterIQ.from_dict(
        {
            "current_chlorine": 0.5,
            "current_ORP": 700,
            "current_SensorLife_Percentage": 95.0,
        }
    )
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.connectedspa_ddeeff_ph").state == "0.0"
    assert hass.states.get("sensor.connectedspa_ddeeff_chlorine").state == "0.5"
    assert (
        hass.states.get(
            "sensor.connectedspa_ddeeff_oxidation_reduction_potential"
        ).state
        == "700"
    )


async def test_freshwater_iq_poll_failure_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    mock_hotspring: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test FreshWater IQ sensors become unavailable on poll failure and recover."""
    _enable_freshwater_iq(device_fixture)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.connectedspa_ddeeff_chlorine").state == "23.1"

    mock_hotspring.update.side_effect = HotSpringConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id, _ in ENTITY_IDS:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_hotspring.update.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for entity_id, expected_state in ENTITY_IDS:
        assert hass.states.get(entity_id).state == expected_state
