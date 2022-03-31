"""Tests for the oncue sensor."""
from __future__ import annotations

from homeassistant.components import oncue
from homeassistant.components.oncue.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import _patch_login_and_data

from tests.common import MockConfigEntry


async def test_sensors(hass: HomeAssistant) -> None:
    """Test that the sensors are setup with the expected values."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "any", CONF_PASSWORD: "any"},
        unique_id="any",
    )
    config_entry.add_to_hass(hass)
    with _patch_login_and_data():
        await async_setup_component(hass, oncue.DOMAIN, {oncue.DOMAIN: {}})
        await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    assert len(hass.states.async_all("sensor")) == 25
    assert hass.states.get("sensor.my_generator_latest_firmware").state == "2.0.6"

    assert hass.states.get("sensor.my_generator_engine_speed").state == "0"

    assert hass.states.get("sensor.my_generator_engine_oil_pressure").state == "0"

    assert (
        hass.states.get("sensor.my_generator_engine_coolant_temperature").state == "0"
    )

    assert hass.states.get("sensor.my_generator_battery_voltage").state == "13.4"

    assert hass.states.get("sensor.my_generator_lube_oil_temperature").state == "0"

    assert (
        hass.states.get("sensor.my_generator_generator_controller_temperature").state
        == "29.0"
    )

    assert (
        hass.states.get("sensor.my_generator_engine_compartment_temperature").state
        == "17.0"
    )

    assert (
        hass.states.get("sensor.my_generator_generator_true_total_power").state == "0.0"
    )

    assert (
        hass.states.get(
            "sensor.my_generator_generator_true_percent_of_rated_power"
        ).state
        == "0"
    )

    assert (
        hass.states.get(
            "sensor.my_generator_generator_voltage_average_line_to_line"
        ).state
        == "0.0"
    )

    assert hass.states.get("sensor.my_generator_generator_frequency").state == "0.0"

    assert hass.states.get("sensor.my_generator_generator_state").state == "Off"

    assert (
        hass.states.get(
            "sensor.my_generator_generator_controller_total_operation_time"
        ).state
        == "16770.8"
    )

    assert hass.states.get("sensor.my_generator_engine_total_run_time").state == "28.1"

    assert (
        hass.states.get("sensor.my_generator_ats_contactor_position").state == "Source1"
    )

    assert hass.states.get("sensor.my_generator_ip_address").state == "1.2.3.4:1026"

    assert (
        hass.states.get("sensor.my_generator_connected_server_ip_address").state
        == "40.117.195.28"
    )

    assert hass.states.get("sensor.my_generator_engine_target_speed").state == "0"

    assert (
        hass.states.get("sensor.my_generator_engine_total_run_time_loaded").state
        == "5.5"
    )

    assert (
        hass.states.get(
            "sensor.my_generator_source1_voltage_average_line_to_line"
        ).state
        == "253.5"
    )

    assert (
        hass.states.get(
            "sensor.my_generator_source2_voltage_average_line_to_line"
        ).state
        == "0.0"
    )

    assert (
        hass.states.get("sensor.my_generator_genset_total_energy").state
        == "1.2022309E7"
    )
    assert (
        hass.states.get("sensor.my_generator_engine_total_number_of_starts").state
        == "101"
    )
    assert (
        hass.states.get("sensor.my_generator_generator_current_average").state == "0.0"
    )
