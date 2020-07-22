"""Tests for the Bond fan device."""
from datetime import timedelta

from bond import DeviceTypes, Directions

from homeassistant import core
from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_SPEED_LIST,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_DIRECTION,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import utcnow

from .common import setup_platform

from tests.async_mock import patch
from tests.common import async_fire_time_changed


def ceiling_fan(name: str):
    """Create a ceiling fan with given name."""
    return {
        "name": name,
        "type": DeviceTypes.CEILING_FAN,
        "actions": ["SetSpeed", "SetDirection"],
    }


async def turn_fan_on(hass: core.HomeAssistant, fan_id: str, speed: str) -> None:
    """Turn the fan on at the specified speed."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_id, fan.ATTR_SPEED: speed},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_entity_registry(hass: core.HomeAssistant):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    registry: EntityRegistry = await hass.helpers.entity_registry.async_get_registry()
    assert [key for key in registry.entities] == ["fan.name_1"]


async def test_entity_non_standard_speed_list(hass: core.HomeAssistant):
    """Tests that the device is registered with custom speed list if number of supported speeds differs form 3."""
    await setup_platform(
        hass,
        FAN_DOMAIN,
        ceiling_fan("name-1"),
        bond_device_id="test-device-id",
        props={"max_speed": 6},
    )

    actual_speeds = hass.states.get("fan.name_1").attributes[ATTR_SPEED_LIST]
    assert actual_speeds == [
        fan.SPEED_OFF,
        fan.SPEED_LOW,
        fan.SPEED_MEDIUM,
        fan.SPEED_HIGH,
    ]

    with patch("homeassistant.components.bond.Bond.turnOn"), patch(
        "homeassistant.components.bond.Bond.setSpeed"
    ) as mock_set_speed_low:
        await turn_fan_on(hass, "fan.name_1", fan.SPEED_LOW)
    mock_set_speed_low.assert_called_once_with("test-device-id", speed=1)

    with patch("homeassistant.components.bond.Bond.turnOn"), patch(
        "homeassistant.components.bond.Bond.setSpeed"
    ) as mock_set_speed_medium:
        await turn_fan_on(hass, "fan.name_1", fan.SPEED_MEDIUM)
    mock_set_speed_medium.assert_called_once_with("test-device-id", speed=3)

    with patch("homeassistant.components.bond.Bond.turnOn"), patch(
        "homeassistant.components.bond.Bond.setSpeed"
    ) as mock_set_speed_high:
        await turn_fan_on(hass, "fan.name_1", fan.SPEED_HIGH)
    mock_set_speed_high.assert_called_once_with("test-device-id", speed=6)


async def test_turn_on_fan(hass: core.HomeAssistant):
    """Tests that turn on command delegates to API."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch("homeassistant.components.bond.Bond.turnOn") as mock_turn_on, patch(
        "homeassistant.components.bond.Bond.setSpeed"
    ) as mock_set_speed:
        await turn_fan_on(hass, "fan.name_1", fan.SPEED_LOW)

    mock_set_speed.assert_called_once()
    mock_turn_on.assert_called_once()


async def test_turn_off_fan(hass: core.HomeAssistant):
    """Tests that turn off command delegates to API."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch("homeassistant.components.bond.Bond.turnOff") as mock_turn_off:
        await hass.services.async_call(
            FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "fan.name_1"}, blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_off.assert_called_once()


async def test_update_reports_fan_on(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports fan power is on."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState",
        return_value={"power": 1, "speed": 1},
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == "on"


async def test_update_reports_fan_off(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports fan power is off."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState",
        return_value={"power": 0, "speed": 1},
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == "off"


async def test_update_reports_direction_forward(hass: core.HomeAssistant):
    """Tests that update command sets correct direction when Bond API reports fan direction is forward."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState",
        return_value={"direction": Directions.FORWARD},
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").attributes[ATTR_DIRECTION] == DIRECTION_FORWARD


async def test_update_reports_direction_reverse(hass: core.HomeAssistant):
    """Tests that update command sets correct direction when Bond API reports fan direction is reverse."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState",
        return_value={"direction": Directions.REVERSE},
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").attributes[ATTR_DIRECTION] == DIRECTION_REVERSE


async def test_set_fan_direction(hass: core.HomeAssistant):
    """Tests that set direction command delegates to API."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch("homeassistant.components.bond.Bond.setDirection") as mock_set_direction:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_DIRECTION,
            {ATTR_ENTITY_ID: "fan.name_1", ATTR_DIRECTION: DIRECTION_FORWARD},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_direction.assert_called_once()
