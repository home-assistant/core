"""Tests for the Bond fan device."""
from __future__ import annotations

from datetime import timedelta

from bond_api import Action, DeviceType, Direction

from homeassistant import core
from homeassistant.components import fan
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_SPEED,
    ATTR_SPEED_LIST,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_SPEED,
    SPEED_OFF,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import utcnow

from .common import (
    help_test_entity_available,
    patch_bond_action,
    patch_bond_device_state,
    setup_platform,
)

from tests.common import async_fire_time_changed


def ceiling_fan(name: str):
    """Create a ceiling fan with given name."""
    return {
        "name": name,
        "type": DeviceType.CEILING_FAN,
        "actions": ["SetSpeed", "SetDirection"],
    }


async def turn_fan_on(
    hass: core.HomeAssistant,
    fan_id: str,
    speed: str | None = None,
    percentage: int | None = None,
) -> None:
    """Turn the fan on at the specified speed."""
    service_data = {ATTR_ENTITY_ID: fan_id}
    if speed:
        service_data[fan.ATTR_SPEED] = speed
    if percentage:
        service_data[fan.ATTR_PERCENTAGE] = percentage
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        service_data=service_data,
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_entity_registry(hass: core.HomeAssistant):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(
        hass,
        FAN_DOMAIN,
        ceiling_fan("name-1"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["fan.name_1"]
    assert entity.unique_id == "test-hub-id_test-device-id"


async def test_non_standard_speed_list(hass: core.HomeAssistant):
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

    with patch_bond_device_state():
        with patch_bond_action() as mock_set_speed_low:
            await turn_fan_on(hass, "fan.name_1", fan.SPEED_LOW)
        mock_set_speed_low.assert_called_once_with(
            "test-device-id", Action.set_speed(2)
        )

        with patch_bond_action() as mock_set_speed_medium:
            await turn_fan_on(hass, "fan.name_1", fan.SPEED_MEDIUM)
        mock_set_speed_medium.assert_called_once_with(
            "test-device-id", Action.set_speed(4)
        )

        with patch_bond_action() as mock_set_speed_high:
            await turn_fan_on(hass, "fan.name_1", fan.SPEED_HIGH)
        mock_set_speed_high.assert_called_once_with(
            "test-device-id", Action.set_speed(6)
        )


async def test_fan_speed_with_no_max_seed(hass: core.HomeAssistant):
    """Tests that fans without max speed (increase/decrease controls) map speed to HA standard."""
    await setup_platform(
        hass,
        FAN_DOMAIN,
        ceiling_fan("name-1"),
        bond_device_id="test-device-id",
        props={"no": "max_speed"},
        state={"power": 1, "speed": 14},
    )

    assert hass.states.get("fan.name_1").attributes["speed"] == fan.SPEED_HIGH


async def test_turn_on_fan_with_speed(hass: core.HomeAssistant):
    """Tests that turn on command delegates to set speed API."""
    await setup_platform(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_set_speed, patch_bond_device_state():
        await turn_fan_on(hass, "fan.name_1", fan.SPEED_LOW)

    mock_set_speed.assert_called_with("test-device-id", Action.set_speed(1))


async def test_turn_on_fan_with_percentage_3_speeds(hass: core.HomeAssistant):
    """Tests that turn on command delegates to set speed API."""
    await setup_platform(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_set_speed, patch_bond_device_state():
        await turn_fan_on(hass, "fan.name_1", percentage=10)

    mock_set_speed.assert_called_with("test-device-id", Action.set_speed(1))

    mock_set_speed.reset_mock()
    with patch_bond_action() as mock_set_speed, patch_bond_device_state():
        await turn_fan_on(hass, "fan.name_1", percentage=50)

    mock_set_speed.assert_called_with("test-device-id", Action.set_speed(2))

    mock_set_speed.reset_mock()
    with patch_bond_action() as mock_set_speed, patch_bond_device_state():
        await turn_fan_on(hass, "fan.name_1", percentage=100)

    mock_set_speed.assert_called_with("test-device-id", Action.set_speed(3))


async def test_turn_on_fan_with_percentage_6_speeds(hass: core.HomeAssistant):
    """Tests that turn on command delegates to set speed API."""
    await setup_platform(
        hass,
        FAN_DOMAIN,
        ceiling_fan("name-1"),
        bond_device_id="test-device-id",
        props={"max_speed": 6},
    )

    with patch_bond_action() as mock_set_speed, patch_bond_device_state():
        await turn_fan_on(hass, "fan.name_1", percentage=10)

    mock_set_speed.assert_called_with("test-device-id", Action.set_speed(1))

    mock_set_speed.reset_mock()
    with patch_bond_action() as mock_set_speed, patch_bond_device_state():
        await turn_fan_on(hass, "fan.name_1", percentage=50)

    mock_set_speed.assert_called_with("test-device-id", Action.set_speed(3))

    mock_set_speed.reset_mock()
    with patch_bond_action() as mock_set_speed, patch_bond_device_state():
        await turn_fan_on(hass, "fan.name_1", percentage=100)

    mock_set_speed.assert_called_with("test-device-id", Action.set_speed(6))


async def test_turn_on_fan_without_speed(hass: core.HomeAssistant):
    """Tests that turn on command delegates to turn on API."""
    await setup_platform(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_on, patch_bond_device_state():
        await turn_fan_on(hass, "fan.name_1")

    mock_turn_on.assert_called_with("test-device-id", Action.turn_on())


async def test_turn_on_fan_with_off_speed(hass: core.HomeAssistant):
    """Tests that turn on command delegates to turn off API."""
    await setup_platform(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_off, patch_bond_device_state():
        await turn_fan_on(hass, "fan.name_1", fan.SPEED_OFF)

    mock_turn_off.assert_called_with("test-device-id", Action.turn_off())


async def test_set_speed_off(hass: core.HomeAssistant):
    """Tests that set_speed(off) command delegates to turn off API."""
    await setup_platform(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_off, patch_bond_device_state():
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_SPEED,
            service_data={ATTR_ENTITY_ID: "fan.name_1", ATTR_SPEED: SPEED_OFF},
            blocking=True,
        )
    await hass.async_block_till_done()

    mock_turn_off.assert_called_with("test-device-id", Action.turn_off())


async def test_turn_off_fan(hass: core.HomeAssistant):
    """Tests that turn off command delegates to API."""
    await setup_platform(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_off, patch_bond_device_state():
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_off.assert_called_once_with("test-device-id", Action.turn_off())


async def test_update_reports_fan_on(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports fan power is on."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"power": 1, "speed": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == "on"


async def test_update_reports_fan_off(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports fan power is off."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"power": 0, "speed": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").state == "off"


async def test_update_reports_direction_forward(hass: core.HomeAssistant):
    """Tests that update command sets correct direction when Bond API reports fan direction is forward."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"direction": Direction.FORWARD}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").attributes[ATTR_DIRECTION] == DIRECTION_FORWARD


async def test_update_reports_direction_reverse(hass: core.HomeAssistant):
    """Tests that update command sets correct direction when Bond API reports fan direction is reverse."""
    await setup_platform(hass, FAN_DOMAIN, ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"direction": Direction.REVERSE}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("fan.name_1").attributes[ATTR_DIRECTION] == DIRECTION_REVERSE


async def test_set_fan_direction(hass: core.HomeAssistant):
    """Tests that set direction command delegates to API."""
    await setup_platform(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_set_direction, patch_bond_device_state():
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_DIRECTION,
            {ATTR_ENTITY_ID: "fan.name_1", ATTR_DIRECTION: DIRECTION_FORWARD},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_set_direction.assert_called_once_with(
        "test-device-id", Action.set_direction(Direction.FORWARD)
    )


async def test_fan_available(hass: core.HomeAssistant):
    """Tests that available state is updated based on API errors."""
    await help_test_entity_available(
        hass, FAN_DOMAIN, ceiling_fan("name-1"), "fan.name_1"
    )
