"""Tests for the Plugwise Sensor integration."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_registry import async_get

from tests.common import MockConfigEntry


async def test_adam_climate_sensor_entities(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of climate related sensor entities."""
    state = hass.states.get("sensor.adam_outdoor_temperature")
    assert state
    assert float(state.state) == 7.81

    state = hass.states.get("sensor.cv_pomp_electricity_consumed")
    assert state
    assert float(state.state) == 35.6

    state = hass.states.get("sensor.onoff_water_temperature")
    assert state
    assert float(state.state) == 70.0

    state = hass.states.get("sensor.cv_pomp_electricity_consumed_interval")
    assert state
    assert float(state.state) == 7.37

    await async_update_entity(hass, "sensor.zone_lisa_wk_battery")

    state = hass.states.get("sensor.zone_lisa_wk_battery")
    assert state
    assert int(state.state) == 34


async def test_anna_as_smt_climate_sensor_entities(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of climate related sensor entities."""
    state = hass.states.get("sensor.opentherm_outdoor_air_temperature")
    assert state
    assert float(state.state) == 3.0

    state = hass.states.get("sensor.opentherm_water_temperature")
    assert state
    assert float(state.state) == 29.1

    state = hass.states.get("sensor.opentherm_dhw_setpoint")
    assert state
    assert float(state.state) == 60.0

    state = hass.states.get("sensor.opentherm_dhw_temperature")
    assert state
    assert float(state.state) == 46.3

    state = hass.states.get("sensor.anna_illuminance")
    assert state
    assert float(state.state) == 86.0


async def test_anna_climate_sensor_entities(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of climate related sensor entities."""
    state = hass.states.get("sensor.opentherm_outdoor_air_temperature")
    assert state
    assert float(state.state) == 3.0


async def test_p1_dsmr_sensor_entities(
    hass: HomeAssistant, mock_smile_p1: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of power related sensor entities."""
    state = hass.states.get("sensor.p1_net_electricity_point")
    assert state
    assert float(state.state) == -2816.0

    state = hass.states.get("sensor.p1_electricity_consumed_off_peak_cumulative")
    assert state
    assert float(state.state) == 551.09

    state = hass.states.get("sensor.p1_electricity_produced_peak_point")
    assert state
    assert float(state.state) == 2816.0

    state = hass.states.get("sensor.p1_electricity_consumed_peak_cumulative")
    assert state
    assert float(state.state) == 442.932

    state = hass.states.get("sensor.p1_gas_consumed_cumulative")
    assert state
    assert float(state.state) == 584.85


async def test_p1_3ph_dsmr_sensor_entities(
    hass: HomeAssistant, mock_smile_p1_2: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of power related sensor entities."""
    state = hass.states.get("sensor.p1_electricity_phase_one_consumed")
    assert state
    assert float(state.state) == 1763.0

    state = hass.states.get("sensor.p1_electricity_phase_two_consumed")
    assert state
    assert float(state.state) == 1703.0

    state = hass.states.get("sensor.p1_electricity_phase_three_consumed")
    assert state
    assert float(state.state) == 2080.0

    entity_id = "sensor.p1_voltage_phase_one"
    state = hass.states.get(entity_id)
    assert not state

    entity_registry = async_get(hass)
    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    await hass.async_block_till_done()

    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.p1_voltage_phase_one")
    assert state
    assert float(state.state) == 233.2


async def test_stretch_sensor_entities(
    hass: HomeAssistant, mock_stretch: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of power related sensor entities."""
    state = hass.states.get("sensor.koelkast_92c4a_electricity_consumed")
    assert state
    assert float(state.state) == 50.5

    state = hass.states.get("sensor.droger_52559_electricity_consumed_interval")
    assert state
    assert float(state.state) == 0.0
