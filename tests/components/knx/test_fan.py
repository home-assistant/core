"""Test KNX fan."""
from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import FanSchema
from homeassistant.const import CONF_NAME, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit


async def test_fan_percent(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX fan with percentage speed."""
    await knx.setup_integration(
        {
            FanSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
            }
        }
    )
    assert len(hass.states.async_all()) == 1

    # turn on fan with default speed (50%)
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (128,))

    # turn off fan
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (0,))

    # receive 100% telegram
    await knx.receive_write("1/2/3", (0xFF,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON

    # receive 80% telegram
    await knx.receive_write("1/2/3", (0xCC,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get("percentage") == 80

    # receive 0% telegram
    await knx.receive_write("1/2/3", (0,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF

    # fan does not respond to read
    await knx.receive_read("1/2/3")
    await knx.assert_telegram_count(0)


async def test_fan_step(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX fan with speed steps."""
    await knx.setup_integration(
        {
            FanSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/2/3",
                FanSchema.CONF_MAX_STEP: 4,
            }
        }
    )
    assert len(hass.states.async_all()) == 1

    # turn on fan with default speed (50% - step 2)
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (2,))

    # turn up speed to 75% - step 3
    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.test", "percentage": 75}, blocking=True
    )
    await knx.assert_write("1/2/3", (3,))

    # turn off fan
    await hass.services.async_call(
        "fan", "turn_off", {"entity_id": "fan.test"}, blocking=True
    )
    await knx.assert_write("1/2/3", (0,))

    # receive step 4 (100%) telegram
    await knx.receive_write("1/2/3", (4,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get("percentage") == 100

    # receive step 1 (25%) telegram
    await knx.receive_write("1/2/3", (1,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get("percentage") == 25

    # receive step 0 (off) telegram
    await knx.receive_write("1/2/3", (0,))
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF

    # fan does not respond to read
    await knx.receive_read("1/2/3")
    await knx.assert_telegram_count(0)


async def test_fan_oscillation(hass: HomeAssistant, knx: KNXTestKit):
    """Test KNX fan oscillation."""
    await knx.setup_integration(
        {
            FanSchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/1/1",
                FanSchema.CONF_OSCILLATION_ADDRESS: "2/2/2",
            }
        }
    )
    assert len(hass.states.async_all()) == 1

    # turn on oscillation
    await hass.services.async_call(
        "fan",
        "oscillate",
        {"entity_id": "fan.test", "oscillating": True},
        blocking=True,
    )
    await knx.assert_write("2/2/2", True)

    # turn off oscillation
    await hass.services.async_call(
        "fan",
        "oscillate",
        {"entity_id": "fan.test", "oscillating": False},
        blocking=True,
    )
    await knx.assert_write("2/2/2", False)

    # receive oscillation on
    await knx.receive_write("2/2/2", True)
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is True

    # receive oscillation off
    await knx.receive_write("2/2/2", False)
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is False
