"""Tests for emulated_kasa library bindings."""
import math

from homeassistant.components import emulated_kasa
from homeassistant.components.emulated_kasa.const import CONF_POWER, DOMAIN
from homeassistant.components.fan import (
    ATTR_SPEED,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_SPEED,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITIES,
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, Mock, patch

ENTITY_SWITCH = "switch.ac"
ENTITY_SWITCH_NAME = "A/C"
ENTITY_SWITCH_POWER = 400.0
ENTITY_LIGHT = "light.bed_light"
ENTITY_LIGHT_NAME = "Bed Room Lights"
ENTITY_FAN = "fan.ceiling_fan"
ENTITY_FAN_NAME = "Ceiling Fan"
ENTITY_FAN_SPEED_LOW = 5
ENTITY_FAN_SPEED_MED = 10
ENTITY_FAN_SPEED_HIGH = 50
ENTITY_SENSOR = "sensor.light_power"

CONFIG = {
    DOMAIN: {
        CONF_ENTITIES: {
            ENTITY_SWITCH: {
                CONF_NAME: ENTITY_SWITCH_NAME,
                CONF_POWER: ENTITY_SWITCH_POWER,
            },
            ENTITY_LIGHT: {CONF_NAME: ENTITY_LIGHT_NAME, CONF_POWER: ENTITY_SENSOR},
            ENTITY_FAN: {
                CONF_POWER: "{% if is_state_attr('"
                + ENTITY_FAN
                + "','speed', 'low') %} "
                + str(ENTITY_FAN_SPEED_LOW)
                + "{% elif is_state_attr('"
                + ENTITY_FAN
                + "','speed', 'medium') %} "
                + str(ENTITY_FAN_SPEED_MED)
                + "{% elif is_state_attr('"
                + ENTITY_FAN
                + "','speed', 'high') %} "
                + str(ENTITY_FAN_SPEED_HIGH)
                + "{% endif %}"
            },
        }
    }
}

CONFIG_SWITCH = {
    DOMAIN: {
        CONF_ENTITIES: {
            ENTITY_SWITCH: {
                CONF_NAME: ENTITY_SWITCH_NAME,
                CONF_POWER: ENTITY_SWITCH_POWER,
            },
        }
    }
}

CONFIG_LIGHT = {
    DOMAIN: {
        CONF_ENTITIES: {
            ENTITY_LIGHT: {CONF_NAME: ENTITY_LIGHT_NAME, CONF_POWER: ENTITY_SENSOR},
        }
    }
}

CONFIG_FAN = {
    DOMAIN: {
        CONF_ENTITIES: {
            ENTITY_FAN: {
                CONF_POWER: "{% if is_state_attr('"
                + ENTITY_FAN
                + "','speed', 'low') %} "
                + str(ENTITY_FAN_SPEED_LOW)
                + "{% elif is_state_attr('"
                + ENTITY_FAN
                + "','speed', 'medium') %} "
                + str(ENTITY_FAN_SPEED_MED)
                + "{% elif is_state_attr('"
                + ENTITY_FAN
                + "','speed', 'high') %} "
                + str(ENTITY_FAN_SPEED_HIGH)
                + "{% endif %}"
            },
        }
    }
}


def nested_value(ndict, *keys):
    """Return a nested dict value  or None if it doesn't exist."""
    if len(keys) == 0:
        return ndict
    key = keys[0]
    if not isinstance(ndict, dict) or key not in ndict:
        return None
    return nested_value(ndict[key], *keys[1:])


async def test_setup(hass):
    """Test that devices are reported correctly."""
    with patch(
        "sense_energy.SenseLink",
        return_value=Mock(start=AsyncMock(), close=AsyncMock()),
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG) is True


async def test_float(hass):
    """Test a configuration using a simple float."""
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: {"platform": "demo"}},
    )
    with patch(
        "sense_energy.SenseLink",
        return_value=Mock(start=AsyncMock(), close=AsyncMock()),
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG_SWITCH) is True
    await hass.async_block_till_done()

    # Turn switch on
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SWITCH}, blocking=True
    )

    switch = hass.states.get(ENTITY_SWITCH)
    assert switch.state == STATE_ON

    plug_it = emulated_kasa.get_plug_devices(hass, CONFIG_SWITCH[DOMAIN][CONF_ENTITIES])
    plug = next(plug_it).generate_response()

    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_SWITCH_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, ENTITY_SWITCH_POWER)

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_SWITCH}, blocking=True
    )

    plug_it = emulated_kasa.get_plug_devices(hass, CONFIG_SWITCH[DOMAIN][CONF_ENTITIES])
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_SWITCH_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, 0)


async def test_template(hass):
    """Test a configuration using a complex template."""
    assert await async_setup_component(
        hass, FAN_DOMAIN, {FAN_DOMAIN: {"platform": "demo", "name": ENTITY_FAN_NAME}}
    )
    with patch(
        "sense_energy.SenseLink",
        return_value=Mock(start=AsyncMock(), close=AsyncMock()),
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG_FAN) is True
    await hass.async_block_till_done()

    # Turn all devices on to known state
    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_FAN}, blocking=True
    )
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_SPEED,
        {ATTR_ENTITY_ID: ENTITY_FAN, ATTR_SPEED: "low"},
        blocking=True,
    )

    fan = hass.states.get(ENTITY_FAN)
    assert fan.state == STATE_ON

    # Fan low:
    plug_it = emulated_kasa.get_plug_devices(hass, CONFIG_FAN[DOMAIN][CONF_ENTITIES])
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_FAN_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, ENTITY_FAN_SPEED_LOW)

    # Fan High:
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_SPEED,
        {ATTR_ENTITY_ID: ENTITY_FAN, ATTR_SPEED: "high"},
        blocking=True,
    )
    plug_it = emulated_kasa.get_plug_devices(hass, CONFIG_FAN[DOMAIN][CONF_ENTITIES])
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_FAN_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, ENTITY_FAN_SPEED_HIGH)

    # Fan off:
    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_FAN}, blocking=True
    )
    plug_it = emulated_kasa.get_plug_devices(hass, CONFIG_FAN[DOMAIN][CONF_ENTITIES])
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_FAN_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, 0)


async def test_sensor(hass):
    """Test a configuration using a sensor in a template."""
    assert await async_setup_component(
        hass, LIGHT_DOMAIN, {LIGHT_DOMAIN: {"platform": "demo", "name": "bed_light"}}
    )
    with patch(
        "sense_energy.SenseLink",
        return_value=Mock(start=AsyncMock(), close=AsyncMock()),
    ):
        assert await async_setup_component(hass, DOMAIN, CONFIG_LIGHT) is True
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_LIGHT}, blocking=True
    )
    hass.states.async_set(ENTITY_SENSOR, 35)

    light = hass.states.get(ENTITY_LIGHT)
    assert light.state == STATE_ON
    sensor = hass.states.get(ENTITY_SENSOR)
    assert sensor.state == "35"

    # light
    plug_it = emulated_kasa.get_plug_devices(hass, CONFIG_LIGHT[DOMAIN][CONF_ENTITIES])
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_LIGHT_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, 35)

    # change power sensor
    hass.states.async_set(ENTITY_SENSOR, 40)

    plug_it = emulated_kasa.get_plug_devices(hass, CONFIG_LIGHT[DOMAIN][CONF_ENTITIES])
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_LIGHT_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, 40)

    # report 0 if device is off
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_LIGHT}, blocking=True
    )

    plug_it = emulated_kasa.get_plug_devices(hass, CONFIG_LIGHT[DOMAIN][CONF_ENTITIES])
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_LIGHT_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, 0)


async def test_multiple_devices(hass):
    """Test that devices are reported correctly."""
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: {"platform": "demo", "name": "heater"}}
    )
    assert await async_setup_component(
        hass, LIGHT_DOMAIN, {LIGHT_DOMAIN: {"platform": "demo", "name": "bed_light"}}
    )
    assert await async_setup_component(
        hass, FAN_DOMAIN, {FAN_DOMAIN: {"platform": "demo", "name": ENTITY_FAN_NAME}}
    )
    with patch(
        "sense_energy.SenseLink",
        return_value=Mock(start=AsyncMock(), close=AsyncMock()),
    ):
        assert await emulated_kasa.async_setup(hass, CONFIG) is True
    await hass.async_block_till_done()

    # Turn all devices on to known state
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SWITCH}, blocking=True
    )
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_LIGHT}, blocking=True
    )
    hass.states.async_set(ENTITY_SENSOR, 35)
    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_FAN}, blocking=True
    )
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_SPEED,
        {ATTR_ENTITY_ID: ENTITY_FAN, ATTR_SPEED: "medium"},
        blocking=True,
    )

    # All of them should now be on
    switch = hass.states.get(ENTITY_SWITCH)
    assert switch.state == STATE_ON
    light = hass.states.get(ENTITY_LIGHT)
    assert light.state == STATE_ON
    sensor = hass.states.get(ENTITY_SENSOR)
    assert sensor.state == "35"
    fan = hass.states.get(ENTITY_FAN)
    assert fan.state == STATE_ON

    plug_it = emulated_kasa.get_plug_devices(hass, CONFIG[DOMAIN][CONF_ENTITIES])
    # switch
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_SWITCH_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, ENTITY_SWITCH_POWER)

    # light
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_LIGHT_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, 35)

    # fan
    plug = next(plug_it).generate_response()
    assert nested_value(plug, "system", "get_sysinfo", "alias") == ENTITY_FAN_NAME
    power = nested_value(plug, "emeter", "get_realtime", "power")
    assert math.isclose(power, ENTITY_FAN_SPEED_MED)

    # No more devices
    assert next(plug_it, None) is None
