"""Test KNX climate."""

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.knx.schema import ClimateSchema
from homeassistant.const import CONF_NAME, STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.common import async_capture_events

RAW_FLOAT_20_0 = (0x07, 0xD0)
RAW_FLOAT_21_0 = (0x0C, 0x1A)
RAW_FLOAT_22_0 = (0x0C, 0x4C)


async def test_climate_basic_temperature_set(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test KNX climate basic."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
            }
        }
    )
    events = async_capture_events(hass, "state_changed")

    # read temperature
    await knx.assert_read("1/2/3")
    # read target temperature
    await knx.assert_read("1/2/5")
    # StateUpdater initialize state
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    events.clear()

    # set new temperature
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.test", "temperature": 20},
        blocking=True,
    )
    await knx.assert_write("1/2/4", RAW_FLOAT_20_0)
    assert len(events) == 1


@pytest.mark.parametrize("heat_cool_ga", [None, "4/4/4"])
async def test_climate_on_off(
    hass: HomeAssistant, knx: KNXTestKit, heat_cool_ga: str | None
) -> None:
    """Test KNX climate on/off."""
    on_off_ga = "3/3/3"
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_ON_OFF_ADDRESS: on_off_ga,
                ClimateSchema.CONF_ON_OFF_STATE_ADDRESS: "1/2/9",
            }
            | (
                {
                    ClimateSchema.CONF_HEAT_COOL_ADDRESS: heat_cool_ga,
                    ClimateSchema.CONF_HEAT_COOL_STATE_ADDRESS: "1/2/11",
                }
                if heat_cool_ga
                else {}
            )
        }
    )
    # read temperature state
    await knx.assert_read("1/2/3")
    await knx.receive_response("1/2/3", RAW_FLOAT_20_0)
    # read target temperature state
    await knx.assert_read("1/2/5")
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    # read on/off state
    await knx.assert_read("1/2/9")
    await knx.receive_response("1/2/9", 1)
    # read heat/cool state
    if heat_cool_ga:
        await knx.assert_read("1/2/11")
        await knx.receive_response("1/2/11", 0)  # cool

    # turn off
    await hass.services.async_call(
        "climate",
        "turn_off",
        {"entity_id": "climate.test"},
        blocking=True,
    )
    await knx.assert_write(on_off_ga, 0)
    assert hass.states.get("climate.test").state == "off"

    # turn on
    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": "climate.test"},
        blocking=True,
    )
    await knx.assert_write(on_off_ga, 1)
    if heat_cool_ga:
        # does not fall back to default hvac mode after turn_on
        assert hass.states.get("climate.test").state == "cool"
    else:
        assert hass.states.get("climate.test").state == "heat"

    # set hvac mode to off triggers turn_off if no controller_mode is available
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test", "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    await knx.assert_write(on_off_ga, 0)
    assert hass.states.get("climate.test").state == "off"

    # set hvac mode to heat
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test", "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    if heat_cool_ga:
        await knx.assert_write(heat_cool_ga, 1)
        await knx.assert_write(on_off_ga, 1)
    else:
        await knx.assert_write(on_off_ga, 1)
    assert hass.states.get("climate.test").state == "heat"


@pytest.mark.parametrize("on_off_ga", [None, "4/4/4"])
async def test_climate_hvac_mode(
    hass: HomeAssistant, knx: KNXTestKit, on_off_ga: str | None
) -> None:
    """Test KNX climate hvac mode."""
    controller_mode_ga = "3/3/3"
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_CONTROLLER_MODE_ADDRESS: controller_mode_ga,
                ClimateSchema.CONF_CONTROLLER_MODE_STATE_ADDRESS: "1/2/7",
                ClimateSchema.CONF_OPERATION_MODES: ["Auto"],
            }
            | (
                {
                    ClimateSchema.CONF_ON_OFF_ADDRESS: on_off_ga,
                }
                if on_off_ga
                else {}
            )
        }
    )
    # read states state updater
    # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")
    # StateUpdater initialize state
    await knx.receive_response("1/2/3", RAW_FLOAT_20_0)
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (0x01,))

    # turn hvac mode to off - set_hvac_mode() doesn't send to on_off if dedicated hvac mode is available
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test", "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    await knx.assert_write(controller_mode_ga, (0x06,))
    if on_off_ga:
        await knx.assert_write(on_off_ga, 0)
    assert hass.states.get("climate.test").state == "off"

    # set hvac to non default mode
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test", "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await knx.assert_write(controller_mode_ga, (0x03,))
    if on_off_ga:
        await knx.assert_write(on_off_ga, 1)
    assert hass.states.get("climate.test").state == "cool"

    # turn off
    await hass.services.async_call(
        "climate",
        "turn_off",
        {"entity_id": "climate.test"},
        blocking=True,
    )
    if on_off_ga:
        await knx.assert_write(on_off_ga, 0)
    else:
        await knx.assert_write(controller_mode_ga, (0x06,))
    assert hass.states.get("climate.test").state == "off"

    # turn on
    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": "climate.test"},
        blocking=True,
    )
    if on_off_ga:
        await knx.assert_write(on_off_ga, 1)
    else:
        # restore last hvac mode
        await knx.assert_write(controller_mode_ga, (0x03,))
    assert hass.states.get("climate.test").state == "cool"


async def test_climate_heat_cool_read_only(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test KNX climate hvac mode."""
    heat_cool_state_ga = "3/3/3"
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_HEAT_COOL_STATE_ADDRESS: heat_cool_state_ga,
            }
        }
    )
    # read states state updater
    # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")
    # StateUpdater initialize state
    await knx.receive_response("1/2/3", RAW_FLOAT_20_0)
    await knx.receive_response("1/2/5", RAW_FLOAT_20_0)
    await knx.assert_read(heat_cool_state_ga)
    await knx.receive_response(heat_cool_state_ga, True)  # heat

    state = hass.states.get("climate.test")
    assert state.state == "heat"
    assert state.attributes["hvac_modes"] == ["heat"]
    assert state.attributes["hvac_action"] == "heating"

    await knx.receive_write(heat_cool_state_ga, False)  # cool
    state = hass.states.get("climate.test")
    assert state.state == "cool"
    assert state.attributes["hvac_modes"] == ["cool"]
    assert state.attributes["hvac_action"] == "cooling"


async def test_climate_heat_cool_read_only_on_off(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test KNX climate hvac mode."""
    on_off_ga = "2/2/2"
    heat_cool_state_ga = "3/3/3"
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_ON_OFF_ADDRESS: on_off_ga,
                ClimateSchema.CONF_HEAT_COOL_STATE_ADDRESS: heat_cool_state_ga,
            }
        }
    )
    # read states state updater
    # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")
    # StateUpdater initialize state
    await knx.receive_response("1/2/3", RAW_FLOAT_20_0)
    await knx.receive_response("1/2/5", RAW_FLOAT_20_0)
    await knx.assert_read(heat_cool_state_ga)
    await knx.receive_response(heat_cool_state_ga, True)  # heat

    state = hass.states.get("climate.test")
    assert state.state == "off"
    assert set(state.attributes["hvac_modes"]) == {"off", "heat"}
    assert state.attributes["hvac_action"] == "off"

    await knx.receive_write(heat_cool_state_ga, False)  # cool
    state = hass.states.get("climate.test")
    assert state.state == "off"
    assert set(state.attributes["hvac_modes"]) == {"off", "cool"}
    assert state.attributes["hvac_action"] == "off"

    await knx.receive_write(on_off_ga, True)
    state = hass.states.get("climate.test")
    assert state.state == "cool"
    assert set(state.attributes["hvac_modes"]) == {"off", "cool"}
    assert state.attributes["hvac_action"] == "cooling"


async def test_climate_preset_mode(
    hass: HomeAssistant, knx: KNXTestKit, entity_registry: er.EntityRegistry
) -> None:
    """Test KNX climate preset mode."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_OPERATION_MODE_ADDRESS: "1/2/6",
                ClimateSchema.CONF_OPERATION_MODE_STATE_ADDRESS: "1/2/7",
            }
        }
    )

    # StateUpdater initialize state
    # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (0x01,))  # comfort

    knx.assert_state("climate.test", HVACMode.HEAT, preset_mode="comfort")
    # set preset mode
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.test", "preset_mode": "building_protection"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x04,))
    knx.assert_state("climate.test", HVACMode.HEAT, preset_mode="building_protection")

    # set preset mode
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.test", "preset_mode": "economy"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x03,))
    knx.assert_state("climate.test", HVACMode.HEAT, preset_mode="economy")

    assert len(knx.xknx.devices) == 2
    assert len(knx.xknx.devices[0].device_updated_cbs) == 2
    assert len(knx.xknx.devices[1].device_updated_cbs) == 2
    # test removing also removes hooks
    entity_registry.async_remove("climate.test")
    # If we remove the entity the underlying devices should disappear too
    assert len(knx.xknx.devices) == 0


async def test_update_entity(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test update climate entity for KNX."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_OPERATION_MODE_ADDRESS: "1/2/6",
                ClimateSchema.CONF_OPERATION_MODE_STATE_ADDRESS: "1/2/7",
            }
        }
    )
    assert await async_setup_component(hass, "homeassistant", {})

    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")
    # StateUpdater initialize state
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (0x01,))

    # verify update entity retriggers group value reads to the bus
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        target={"entity_id": "climate.test"},
        blocking=True,
    )

    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")
    await knx.assert_read("1/2/7")


async def test_command_value_idle_mode(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX climate command_value."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_COMMAND_VALUE_STATE_ADDRESS: "1/2/6",
            }
        }
    )
    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")
    # StateUpdater initialize state
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)
    # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read("1/2/6")
    await knx.receive_response("1/2/6", (0x32,))

    knx.assert_state("climate.test", HVACMode.HEAT, command_value=20)

    await knx.receive_write("1/2/6", (0x00,))

    knx.assert_state(
        "climate.test", HVACMode.HEAT, command_value=0, hvac_action=STATE_IDLE
    )


async def test_fan_speed_3_steps(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX climate fan speed 3 steps."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_FAN_SPEED_ADDRESS: "1/2/6",
                ClimateSchema.CONF_FAN_SPEED_STATE_ADDRESS: "1/2/7",
                ClimateSchema.CONF_FAN_SPEED_MODE: "step",
                ClimateSchema.CONF_FAN_MAX_STEP: 3,
            }
        }
    )

    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")

    # StateUpdater initialize state
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)

    # Query status
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (0x01,))
    knx.assert_state(
        "climate.test",
        HVACMode.HEAT,
        fan_mode="low",
        fan_modes=["off", "low", "medium", "high"],
    )

    # set fan mode
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "medium"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x02,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="medium")

    # turn off
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "off"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x0,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="off")


async def test_fan_speed_2_steps(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX climate fan speed 2 steps."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_FAN_SPEED_ADDRESS: "1/2/6",
                ClimateSchema.CONF_FAN_SPEED_STATE_ADDRESS: "1/2/7",
                ClimateSchema.CONF_FAN_SPEED_MODE: "step",
                ClimateSchema.CONF_FAN_MAX_STEP: 2,
            }
        }
    )

    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")

    # StateUpdater initialize state
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)

    # Query status
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (0x01,))
    knx.assert_state(
        "climate.test", HVACMode.HEAT, fan_mode="low", fan_modes=["off", "low", "high"]
    )

    # set fan mode
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "high"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x02,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="high")

    # turn off
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "off"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x0,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="off")


async def test_fan_speed_1_step(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX climate fan speed 1 step."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_FAN_SPEED_ADDRESS: "1/2/6",
                ClimateSchema.CONF_FAN_SPEED_STATE_ADDRESS: "1/2/7",
                ClimateSchema.CONF_FAN_SPEED_MODE: "step",
                ClimateSchema.CONF_FAN_MAX_STEP: 1,
            }
        }
    )

    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")

    # StateUpdater initialize state
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)

    # Query status
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (0x01,))
    knx.assert_state(
        "climate.test", HVACMode.HEAT, fan_mode="on", fan_modes=["off", "on"]
    )

    # turn off
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "off"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x0,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="off")


async def test_fan_speed_5_steps(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX climate fan speed 5 steps."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_FAN_SPEED_ADDRESS: "1/2/6",
                ClimateSchema.CONF_FAN_SPEED_STATE_ADDRESS: "1/2/7",
                ClimateSchema.CONF_FAN_SPEED_MODE: "step",
                ClimateSchema.CONF_FAN_MAX_STEP: 5,
            }
        }
    )

    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")

    # StateUpdater initialize state
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)

    # Query status
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (0x01,))
    knx.assert_state(
        "climate.test",
        HVACMode.HEAT,
        fan_mode="1",
        fan_modes=["off", "1", "2", "3", "4", "5"],
    )

    # set fan mode
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "4"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x04,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="4")

    # turn off
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "off"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x0,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="off")


async def test_fan_speed_percentage(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX climate fan speed percentage."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_FAN_SPEED_ADDRESS: "1/2/6",
                ClimateSchema.CONF_FAN_SPEED_STATE_ADDRESS: "1/2/7",
                ClimateSchema.CONF_FAN_SPEED_MODE: "percent",
            }
        }
    )

    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")

    # StateUpdater initialize state
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)

    # Query status
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (84,))  # 84 / 255 = 33%
    knx.assert_state(
        "climate.test",
        HVACMode.HEAT,
        fan_mode="low",
        fan_modes=["off", "low", "medium", "high"],
    )

    # set fan mode
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "medium"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (168,))  # 168 / 255 = 66%
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="medium")

    # turn off
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "off"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x0,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="off")

    # check fan mode that is not in the fan modes list
    await knx.receive_write("1/2/6", (127,))  # 127 / 255 = 50%
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="medium")

    # check FAN_OFF is not picked when fan_speed is closest to zero
    await knx.receive_write("1/2/6", (3,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="low")


async def test_fan_speed_percentage_4_steps(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test KNX climate fan speed percentage with 4 steps."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_FAN_SPEED_ADDRESS: "1/2/6",
                ClimateSchema.CONF_FAN_SPEED_STATE_ADDRESS: "1/2/7",
                ClimateSchema.CONF_FAN_SPEED_MODE: "percent",
                ClimateSchema.CONF_FAN_MAX_STEP: 4,
            }
        }
    )

    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")

    # StateUpdater initialize state
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)

    # Query status
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (64,))  # 64 / 255 = 25%
    knx.assert_state(
        "climate.test",
        HVACMode.HEAT,
        fan_mode="25%",
        fan_modes=["off", "25%", "50%", "75%", "100%"],
    )

    # set fan mode
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "50%"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (128,))  # 128 / 255 = 50%
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="50%")

    # turn off
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "off"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x0,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="off")

    # check fan mode that is not in the fan modes list
    await knx.receive_write("1/2/6", (168,))  # 168 / 255 = 66%
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="75%")


async def test_fan_speed_zero_mode_auto(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX climate fan speed 3 steps."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_FAN_SPEED_ADDRESS: "1/2/6",
                ClimateSchema.CONF_FAN_SPEED_STATE_ADDRESS: "1/2/7",
                ClimateSchema.CONF_FAN_MAX_STEP: 3,
                ClimateSchema.CONF_FAN_SPEED_MODE: "step",
                ClimateSchema.CONF_FAN_ZERO_MODE: "auto",
            }
        }
    )

    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")

    # StateUpdater initialize state
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)

    # Query status
    await knx.assert_read("1/2/7")
    await knx.receive_response("1/2/7", (0x01,))
    knx.assert_state(
        "climate.test",
        HVACMode.HEAT,
        fan_mode="low",
        fan_modes=["auto", "low", "medium", "high"],
    )

    # set auto
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": "climate.test", "fan_mode": "auto"},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x0,))
    knx.assert_state("climate.test", HVACMode.HEAT, fan_mode="auto")
