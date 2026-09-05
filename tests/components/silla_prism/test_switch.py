"""Test the Silla Prism switches."""

from unittest.mock import patch

import pytest

from homeassistant.components.silla_prism.const import (
    CONF_BATTERY_MAX_CHARGE_POWER,
    CONF_BATTERY_POWER_SENSOR,
    CONF_HOME_LOAD_POWER_SENSOR,
    CONF_SOLAR_BALANCE_DRY_RUN,
    CONF_SOLAR_BALANCE_START_DELAY,
    CONF_SOLAR_BATTERY_BALANCE,
    CONF_SOLAR_PRODUCTION_POWER_SENSOR,
    DOMAIN,
)
from homeassistant.components.silla_prism.solar_balance import (
    SOLAR_BALANCE_CHARGING_SURPLUS,
    SOLAR_BALANCE_PAUSED_LOW_SURPLUS,
    SOLAR_BALANCE_WAITING_DATA,
    SOLAR_BALANCE_WAITING_SOLAR_MODE,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import BASE_TOPIC

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient

BATTERY_SENSOR = "sensor.home_battery_power"
SOLAR_SENSOR = "sensor.solar_production_power"
HOME_LOAD_SENSOR = "sensor.home_load_power"
SWITCH_UNIQUE_ID = "prism_solar_battery_balance_001"


def _entity_id(
    entity_registry: er.EntityRegistry, platform: Platform, unique_id: str
) -> str:
    entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


def _solar_balance_config_entry(hass: HomeAssistant, **data: object) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Silla Prism",
        unique_id=BASE_TOPIC,
        data={
            "topic": BASE_TOPIC,
            CONF_SOLAR_BATTERY_BALANCE: True,
            CONF_BATTERY_POWER_SENSOR: BATTERY_SENSOR,
            CONF_SOLAR_PRODUCTION_POWER_SENSOR: SOLAR_SENSOR,
            CONF_HOME_LOAD_POWER_SENSOR: HOME_LOAD_SENSOR,
            CONF_BATTERY_MAX_CHARGE_POWER: 0,
            CONF_SOLAR_BALANCE_START_DELAY: 0,
            **data,
        },
    )
    entry.add_to_hass(hass)
    return entry


async def _setup_solar_balance(
    hass: HomeAssistant, entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> str:
    with patch("homeassistant.components.silla_prism.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, entry)
    return _entity_id(entity_registry, Platform.SWITCH, SWITCH_UNIQUE_ID)


async def _fire_balance_inputs(
    hass: HomeAssistant,
    *,
    grid_power: str = "-3000",
    ev_power: str = "0",
    current_limit: str = "32",
    voltage: str = "230",
    mode: str = "1",
) -> None:
    async_fire_mqtt_message(hass, "prism/energy_data/power_grid", grid_power)
    async_fire_mqtt_message(hass, "prism/1/w", ev_power)
    async_fire_mqtt_message(hass, "prism/1/pilot", current_limit)
    async_fire_mqtt_message(hass, "prism/1/volt", voltage)
    async_fire_mqtt_message(hass, "prism/1/mode", mode)
    await hass.async_block_till_done()
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mqtt_mock")
async def test_solar_balance_only_commands_in_solar_mode(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the balancer waits when Prism is not in solar control mode."""
    entry = _solar_balance_config_entry(hass)
    hass.states.async_set(BATTERY_SENSOR, "0")
    hass.states.async_set(SOLAR_SENSOR, "3500")
    hass.states.async_set(HOME_LOAD_SENSOR, "500")
    await _setup_solar_balance(hass, entry, entity_registry)

    mqtt_mock.async_publish.reset_mock()
    await _fire_balance_inputs(hass, mode="2")

    state = entry.runtime_data.solar_balance_states[1]
    assert state.status == SOLAR_BALANCE_WAITING_SOLAR_MODE
    assert state.theoretical_target_current == 12
    mqtt_mock.async_publish.assert_not_called()

    await _fire_balance_inputs(hass, mode="1")

    state = entry.runtime_data.solar_balance_states[1]
    assert state.status == SOLAR_BALANCE_CHARGING_SURPLUS
    assert state.raw_target_current == 12
    assert state.target_current == 29
    assert tuple(call.args[:2] for call in mqtt_mock.async_publish.call_args_list) == (
        ("prism/1/command/set_current_limit", "29"),
        ("prism/1/command/set_mode", "1"),
    )


@pytest.mark.usefixtures("mqtt_mock")
async def test_solar_balance_low_surplus_pauses_and_restarts_from_minimum(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test low surplus pauses charging and the next recovery starts at 6A."""
    entry = _solar_balance_config_entry(hass)
    hass.states.async_set(BATTERY_SENSOR, "0")
    hass.states.async_set(SOLAR_SENSOR, "900")
    hass.states.async_set(HOME_LOAD_SENSOR, "500")
    await _setup_solar_balance(hass, entry, entity_registry)

    mqtt_mock.async_publish.reset_mock()
    await _fire_balance_inputs(hass, grid_power="1000")

    state = entry.runtime_data.solar_balance_states[1]
    assert state.status == SOLAR_BALANCE_PAUSED_LOW_SURPLUS
    assert state.target_current == 0
    assert tuple(call.args[:2] for call in mqtt_mock.async_publish.call_args_list) == (
        ("prism/1/command/set_current_limit", "6"),
        ("prism/1/command/set_mode", "3"),
    )

    mqtt_mock.async_publish.reset_mock()
    hass.states.async_set(SOLAR_SENSOR, "5000")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = entry.runtime_data.solar_balance_states[1]
    assert state.status == SOLAR_BALANCE_CHARGING_SURPLUS
    assert state.target_current == 6
    assert tuple(call.args[:2] for call in mqtt_mock.async_publish.call_args_list) == (
        ("prism/1/command/set_mode", "1"),
    )


@pytest.mark.usefixtures("mqtt_mock")
async def test_solar_balance_turn_off_does_not_force_normal_mode(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test disabling the balancer does not publish an unrestricted mode."""
    entry = _solar_balance_config_entry(hass)
    switch_entity_id = await _setup_solar_balance(hass, entry, entity_registry)

    mqtt_mock.async_publish.reset_mock()
    switch_entity = hass.data[Platform.SWITCH].get_entity(switch_entity_id)
    assert switch_entity is not None
    await switch_entity.async_turn_off()

    mqtt_mock.async_publish.assert_not_called()


@pytest.mark.usefixtures("mqtt_mock")
async def test_solar_balance_reports_missing_direct_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test missing configured direct sensors are reported specifically."""
    entry = _solar_balance_config_entry(hass, **{CONF_SOLAR_BALANCE_DRY_RUN: True})
    hass.states.async_set(BATTERY_SENSOR, "0")
    hass.states.async_set(SOLAR_SENSOR, "3500")
    await _setup_solar_balance(hass, entry, entity_registry)

    await _fire_balance_inputs(hass)

    state = entry.runtime_data.solar_balance_states[1]
    assert state.status == SOLAR_BALANCE_WAITING_DATA
    assert state.missing_data_reason == "home_load_power"
