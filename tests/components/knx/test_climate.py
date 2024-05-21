"""Test KNX climate."""

import pytest

from homeassistant.components.climate import PRESET_ECO, PRESET_SLEEP, HVACMode
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


@pytest.mark.parametrize("heat_cool", [False, True])
async def test_climate_on_off(
    hass: HomeAssistant, knx: KNXTestKit, heat_cool: bool
) -> None:
    """Test KNX climate on/off."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_ON_OFF_ADDRESS: "1/2/8",
                ClimateSchema.CONF_ON_OFF_STATE_ADDRESS: "1/2/9",
            }
            | (
                {
                    ClimateSchema.CONF_HEAT_COOL_ADDRESS: "1/2/10",
                    ClimateSchema.CONF_HEAT_COOL_STATE_ADDRESS: "1/2/11",
                }
                if heat_cool
                else {}
            )
        }
    )

    await hass.async_block_till_done()
    # read heat/cool state
    if heat_cool:
        await knx.assert_read("1/2/11")
        await knx.receive_response("1/2/11", 0)  # cool
    # read temperature state
    await knx.assert_read("1/2/3")
    await knx.receive_response("1/2/3", RAW_FLOAT_20_0)
    # read target temperature state
    await knx.assert_read("1/2/5")
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    # read on/off state
    await knx.assert_read("1/2/9")
    await knx.receive_response("1/2/9", 1)

    # turn off
    await hass.services.async_call(
        "climate",
        "turn_off",
        {"entity_id": "climate.test"},
        blocking=True,
    )
    await knx.assert_write("1/2/8", 0)
    assert hass.states.get("climate.test").state == "off"

    # turn on
    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": "climate.test"},
        blocking=True,
    )
    await knx.assert_write("1/2/8", 1)
    if heat_cool:
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
    await knx.assert_write("1/2/8", 0)

    # set hvac mode to heat
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test", "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    if heat_cool:
        # only set new hvac_mode without changing on/off - actuator shall handle that
        await knx.assert_write("1/2/10", 1)
    else:
        await knx.assert_write("1/2/8", 1)


async def test_climate_hvac_mode(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX climate hvac mode."""
    await knx.setup_integration(
        {
            ClimateSchema.PLATFORM: {
                CONF_NAME: "test",
                ClimateSchema.CONF_TEMPERATURE_ADDRESS: "1/2/3",
                ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS: "1/2/4",
                ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS: "1/2/5",
                ClimateSchema.CONF_CONTROLLER_MODE_ADDRESS: "1/2/6",
                ClimateSchema.CONF_CONTROLLER_MODE_STATE_ADDRESS: "1/2/7",
                ClimateSchema.CONF_ON_OFF_ADDRESS: "1/2/8",
                ClimateSchema.CONF_OPERATION_MODES: ["Auto"],
            }
        }
    )

    await hass.async_block_till_done()
    # read states state updater
    await knx.assert_read("1/2/7")
    await knx.assert_read("1/2/3")
    # StateUpdater initialize state
    await knx.receive_response("1/2/7", (0x01,))
    await knx.receive_response("1/2/3", RAW_FLOAT_20_0)
    # StateUpdater semaphore allows 2 concurrent requests
    # read target temperature state
    await knx.assert_read("1/2/5")
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)

    # turn hvac mode to off
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test", "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x06,))

    # turn hvac on
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test", "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x01,))


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
    events = async_capture_events(hass, "state_changed")

    await hass.async_block_till_done()
    # read states state updater
    await knx.assert_read("1/2/7")
    await knx.assert_read("1/2/3")
    # StateUpdater initialize state
    await knx.receive_response("1/2/7", (0x01,))
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)
    # StateUpdater semaphore allows 2 concurrent requests
    # read target temperature state
    await knx.assert_read("1/2/5")
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)
    events.clear()

    # set preset mode
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.test", "preset_mode": PRESET_ECO},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x04,))
    assert len(events) == 1
    events.pop()

    # set preset mode
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.test", "preset_mode": PRESET_SLEEP},
        blocking=True,
    )
    await knx.assert_write("1/2/6", (0x03,))
    assert len(events) == 1
    events.pop()

    assert len(knx.xknx.devices) == 2
    assert len(knx.xknx.devices[0].device_updated_cbs) == 2
    assert len(knx.xknx.devices[1].device_updated_cbs) == 2
    # test removing also removes hooks
    entity_registry.async_remove("climate.test")
    await hass.async_block_till_done()

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
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    # read states state updater
    await knx.assert_read("1/2/7")
    await knx.assert_read("1/2/3")
    # StateUpdater initialize state
    await knx.receive_response("1/2/7", (0x01,))
    await knx.receive_response("1/2/3", RAW_FLOAT_21_0)
    # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read("1/2/5")
    await knx.receive_response("1/2/5", RAW_FLOAT_22_0)

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

    await hass.async_block_till_done()
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
