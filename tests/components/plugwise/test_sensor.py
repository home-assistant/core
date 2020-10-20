"""Tests for the Plugwise Sensor integration."""

from homeassistant.config_entries import ENTRY_STATE_LOADED

from tests.components.plugwise.common import async_init_integration


async def test_adam_climate_sensor_entities(hass, mock_smile_adam):
    """Test creation of climate related sensor entities."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state == ENTRY_STATE_LOADED

    state = hass.states.get("sensor.adam_outdoor_temperature")
    assert float(state.state) == 7.81

    state = hass.states.get("sensor.cv_pomp_electricity_consumed")
    assert float(state.state) == 35.6

    state = hass.states.get("sensor.auxiliary_water_temperature")
    assert float(state.state) == 70.0

    state = hass.states.get("sensor.cv_pomp_electricity_consumed_interval")
    assert float(state.state) == 7.37

    await hass.helpers.entity_component.async_update_entity(
        "sensor.zone_lisa_wk_battery"
    )

    state = hass.states.get("sensor.zone_lisa_wk_battery")
    assert float(state.state) == 34


async def test_anna_climate_sensor_entities(hass, mock_smile_anna):
    """Test creation of climate related sensor entities."""
    entry = await async_init_integration(hass, mock_smile_anna)
    assert entry.state == ENTRY_STATE_LOADED

    state = hass.states.get("sensor.auxiliary_outdoor_temperature")
    assert float(state.state) == 18.0

    state = hass.states.get("sensor.auxiliary_water_temperature")
    assert float(state.state) == 29.1

    state = hass.states.get("sensor.anna_illuminance")
    assert float(state.state) == 86.0


async def test_p1_dsmr_sensor_entities(hass, mock_smile_p1):
    """Test creation of power related sensor entities."""
    entry = await async_init_integration(hass, mock_smile_p1)
    assert entry.state == ENTRY_STATE_LOADED

    state = hass.states.get("sensor.p1_net_electricity_point")
    assert float(state.state) == -2761.0

    state = hass.states.get("sensor.p1_electricity_consumed_off_peak_cumulative")
    assert int(state.state) == 551

    state = hass.states.get("sensor.p1_electricity_produced_peak_point")
    assert float(state.state) == 2761.0

    state = hass.states.get("sensor.p1_electricity_consumed_peak_cumulative")
    assert int(state.state) == 442

    state = hass.states.get("sensor.p1_gas_consumed_cumulative")
    assert float(state.state) == 584.9
