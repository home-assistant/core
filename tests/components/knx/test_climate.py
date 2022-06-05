"""Test KNX climate."""
from homeassistant.components.climate.const import PRESET_ECO, PRESET_SLEEP, HVACMode
from homeassistant.components.knx.schema import ClimateSchema
from homeassistant.const import CONF_NAME, STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.common import async_capture_events


async def test_climate_basic_temperature_set(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX climate basic."""
    events = async_capture_events(hass, "state_changed")
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
    assert len(hass.states.async_all()) == 1
    assert len(events) == 1
    events.pop()

    # read temperature
    await knx.assert_read("1/2/3")
    # read target temperature
    await knx.assert_read("1/2/5")

    # set new temperature
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.test", "temperature": 20},
        blocking=True,
    )
    await knx.assert_write("1/2/4", (7, 208))
    assert len(events) == 1
    events.pop()


async def test_climate_hvac_mode(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX climate hvac mode."""
    events = async_capture_events(hass, "state_changed")
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
    assert len(hass.states.async_all()) == 1
    assert len(events) == 1
    events.pop()

    await hass.async_block_till_done()
    # read states state updater
    await knx.assert_read("1/2/7")
    await knx.assert_read("1/2/3")
    # StateUpdater initialize state
    await knx.receive_response("1/2/7", True)
    await knx.receive_response("1/2/3", (0x21,))
    # StateUpdater semaphore allows 2 concurrent requests
    # read target temperature state
    await knx.assert_read("1/2/5")

    # turn hvac off
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test", "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    await knx.assert_write("1/2/8", False)

    # turn hvac on
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.test", "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    await knx.assert_write("1/2/8", True)
    await knx.assert_write("1/2/6", (0x01,))


async def test_climate_preset_mode(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX climate preset mode."""
    events = async_capture_events(hass, "state_changed")
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
    assert len(hass.states.async_all()) == 1
    assert len(events) == 1
    events.pop()

    await hass.async_block_till_done()
    # read states state updater
    await knx.assert_read("1/2/7")
    await knx.assert_read("1/2/3")
    # StateUpdater initialize state
    await knx.receive_response("1/2/7", True)
    await knx.receive_response("1/2/3", (0x01,))
    # StateUpdater semaphore allows 2 concurrent requests
    # read target temperature state
    await knx.assert_read("1/2/5")

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
    er = entity_registry.async_get(hass)
    er.async_remove("climate.test")
    await hass.async_block_till_done()

    # If we remove the entity the underlying devices should disappear too
    assert len(knx.xknx.devices) == 0


async def test_update_entity(hass: HomeAssistant, knx: KNXTestKit):
    """Test update climate entity for KNX."""
    events = async_capture_events(hass, "state_changed")
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
    assert len(hass.states.async_all()) == 1
    assert len(events) == 1
    events.pop()

    await hass.async_block_till_done()
    # read states state updater
    await knx.assert_read("1/2/7")
    await knx.assert_read("1/2/3")
    # StateUpdater initialize state
    await knx.receive_response("1/2/7", True)
    await knx.receive_response("1/2/3", (0x01,))
    # StateUpdater semaphore allows 2 concurrent requests
    await knx.assert_read("1/2/5")

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


async def test_command_value_idle_mode(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX climate command_value."""
    events = async_capture_events(hass, "state_changed")
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
    assert len(hass.states.async_all()) == 1
    assert len(events) == 1
    events.pop()

    await hass.async_block_till_done()
    # read states state updater
    await knx.assert_read("1/2/3")
    await knx.assert_read("1/2/5")
    # StateUpdater initialize state
    await knx.receive_response("1/2/6", (0x32,))
    await knx.receive_response("1/2/3", (0x0C, 0x1A))

    assert len(events) == 2
    events.pop()

    knx.assert_state("climate.test", HVACMode.HEAT, command_value=20)

    await knx.receive_write("1/2/6", (0x00,))

    knx.assert_state(
        "climate.test", HVACMode.HEAT, command_value=0, hvac_action=STATE_IDLE
    )
