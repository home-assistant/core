"""Tests for the Bond button device."""

from bond_async import Action, DeviceType

from homeassistant import core
from homeassistant.components.bond.button import STEP_SIZE
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry

from .common import patch_bond_action, patch_bond_device_state, setup_platform


def ceiling_fan(name: str):
    """Create a ceiling fan with given name."""
    return {
        "name": name,
        "type": DeviceType.CEILING_FAN,
        "actions": [Action.SET_SPEED, Action.SET_DIRECTION, Action.STOP],
    }


def light_brightness_increase_decrease_only(name: str):
    """Create a light that can only increase or decrease brightness."""
    return {
        "name": name,
        "type": DeviceType.LIGHT,
        "actions": [
            Action.TURN_LIGHT_ON,
            Action.TURN_LIGHT_OFF,
            Action.START_DIMMER,
            Action.START_INCREASING_BRIGHTNESS,
            Action.START_DECREASING_BRIGHTNESS,
            Action.STOP,
        ],
    }


def fireplace_increase_decrease_only(name: str):
    """Create a fireplace that can only increase or decrease flame."""
    return {
        "name": name,
        "type": DeviceType.LIGHT,
        "actions": [
            Action.INCREASE_FLAME,
            Action.DECREASE_FLAME,
        ],
    }


def light(name: str):
    """Create a light with a given name."""
    return {
        "name": name,
        "type": DeviceType.LIGHT,
        "actions": [Action.TURN_LIGHT_ON, Action.TURN_LIGHT_OFF, Action.SET_BRIGHTNESS],
    }


async def test_entity_registry(hass: core.HomeAssistant):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(
        hass,
        BUTTON_DOMAIN,
        light_brightness_increase_decrease_only("name-1"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["button.name_1_stop_actions"]
    assert entity.unique_id == "test-hub-id_test-device-id_stop"
    entity = registry.entities["button.name_1_start_increasing_brightness"]
    assert entity.unique_id == "test-hub-id_test-device-id_startincreasingbrightness"
    entity = registry.entities["button.name_1_start_decreasing_brightness"]
    assert entity.unique_id == "test-hub-id_test-device-id_startdecreasingbrightness"
    entity = registry.entities["button.name_1_start_dimmer"]
    assert entity.unique_id == "test-hub-id_test-device-id_startdimmer"


async def test_mutually_exclusive_actions(hass: core.HomeAssistant):
    """Tests we do not create the button when there is a mutually exclusive action."""
    await setup_platform(
        hass,
        BUTTON_DOMAIN,
        light("name-1"),
        bond_device_id="test-device-id",
    )

    assert not hass.states.async_all("button")


async def test_stop_not_created_no_other_buttons(hass: core.HomeAssistant):
    """Tests we do not create the stop button when there are no other buttons."""
    await setup_platform(
        hass,
        BUTTON_DOMAIN,
        ceiling_fan("name-1"),
        bond_device_id="test-device-id",
    )

    assert not hass.states.async_all("button")


async def test_press_button_with_argument(hass: core.HomeAssistant):
    """Tests we can press a button with an argument."""
    await setup_platform(
        hass,
        BUTTON_DOMAIN,
        fireplace_increase_decrease_only("name-1"),
        bond_device_id="test-device-id",
    )

    assert hass.states.get("button.name_1_increase_flame")
    assert hass.states.get("button.name_1_decrease_flame")

    with patch_bond_action() as mock_action, patch_bond_device_state():
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.name_1_increase_flame"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_action.assert_called_once_with(
        "test-device-id", Action(Action.INCREASE_FLAME, STEP_SIZE)
    )

    with patch_bond_action() as mock_action, patch_bond_device_state():
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.name_1_decrease_flame"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_action.assert_called_once_with(
        "test-device-id", Action(Action.DECREASE_FLAME, STEP_SIZE)
    )


async def test_press_button(hass: core.HomeAssistant):
    """Tests we can press a button."""
    await setup_platform(
        hass,
        BUTTON_DOMAIN,
        light_brightness_increase_decrease_only("name-1"),
        bond_device_id="test-device-id",
    )

    assert hass.states.get("button.name_1_start_increasing_brightness")
    assert hass.states.get("button.name_1_start_decreasing_brightness")

    with patch_bond_action() as mock_action, patch_bond_device_state():
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.name_1_start_increasing_brightness"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_action.assert_called_once_with(
        "test-device-id", Action(Action.START_INCREASING_BRIGHTNESS)
    )

    with patch_bond_action() as mock_action, patch_bond_device_state():
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.name_1_start_decreasing_brightness"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_action.assert_called_once_with(
        "test-device-id", Action(Action.START_DECREASING_BRIGHTNESS)
    )
