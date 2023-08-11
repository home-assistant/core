"""Tests for the Bond light device."""
from datetime import timedelta

from bond_async import Action, DeviceType
import pytest

from homeassistant.components.bond.const import (
    ATTR_POWER_STATE,
    DOMAIN,
    SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
    SERVICE_SET_LIGHT_POWER_TRACKED_STATE,
)
from homeassistant.components.bond.light import (
    SERVICE_START_DECREASING_BRIGHTNESS,
    SERVICE_START_INCREASING_BRIGHTNESS,
    SERVICE_STOP,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import utcnow

from .common import (
    help_test_entity_available,
    patch_bond_action,
    patch_bond_action_returns_clientresponseerror,
    patch_bond_device_state,
    setup_platform,
)

from tests.common import async_fire_time_changed


def light(name: str):
    """Create a light with a given name."""
    return {
        "name": name,
        "type": DeviceType.LIGHT,
        "actions": [Action.TURN_LIGHT_ON, Action.TURN_LIGHT_OFF, Action.SET_BRIGHTNESS],
    }


def light_no_brightness(name: str):
    """Create a light with a given name."""
    return {
        "name": name,
        "type": DeviceType.LIGHT,
        "actions": [Action.TURN_LIGHT_ON, Action.TURN_LIGHT_OFF],
    }


def ceiling_fan(name: str):
    """Create a ceiling fan (that has built-in light) with given name."""
    return {
        "name": name,
        "type": DeviceType.CEILING_FAN,
        "actions": [Action.TURN_LIGHT_ON, Action.TURN_LIGHT_OFF],
    }


def dimmable_ceiling_fan(name: str):
    """Create a ceiling fan (that has built-in light) with given name."""
    return {
        "name": name,
        "type": DeviceType.CEILING_FAN,
        "actions": [Action.TURN_LIGHT_ON, Action.TURN_LIGHT_OFF, Action.SET_BRIGHTNESS],
    }


def down_light_ceiling_fan(name: str):
    """Create a ceiling fan (that has built-in down light) with given name."""
    return {
        "name": name,
        "type": DeviceType.CEILING_FAN,
        "actions": [Action.TURN_DOWN_LIGHT_ON, Action.TURN_DOWN_LIGHT_OFF],
    }


def up_light_ceiling_fan(name: str):
    """Create a ceiling fan (that has built-in down light) with given name."""
    return {
        "name": name,
        "type": DeviceType.CEILING_FAN,
        "actions": [Action.TURN_UP_LIGHT_ON, Action.TURN_UP_LIGHT_OFF],
    }


def fireplace(name: str):
    """Create a fireplace with given name."""
    return {
        "name": name,
        "type": DeviceType.FIREPLACE,
        "actions": [Action.TURN_ON, Action.TURN_OFF],
    }


def fireplace_with_light(name: str):
    """Create a fireplace with given name."""
    return {
        "name": name,
        "type": DeviceType.FIREPLACE,
        "actions": [
            Action.TURN_ON,
            Action.TURN_OFF,
            Action.TURN_LIGHT_ON,
            Action.TURN_LIGHT_OFF,
        ],
    }


def fireplace_with_light_supports_brightness(name: str):
    """Create a fireplace with given name."""
    return {
        "name": name,
        "type": DeviceType.FIREPLACE,
        "actions": [
            Action.TURN_ON,
            Action.TURN_OFF,
            Action.TURN_LIGHT_ON,
            Action.TURN_LIGHT_OFF,
            Action.SET_BRIGHTNESS,
        ],
    }


def light_brightness_increase_decrease_only(name: str):
    """Create a light that can only increase or decrease brightness."""
    return {
        "name": name,
        "type": DeviceType.LIGHT,
        "actions": [
            Action.TURN_LIGHT_ON,
            Action.TURN_LIGHT_OFF,
            Action.START_INCREASING_BRIGHTNESS,
            Action.START_DECREASING_BRIGHTNESS,
            Action.STOP,
        ],
    }


async def test_fan_entity_registry(hass: HomeAssistant) -> None:
    """Tests that fan with light devices are registered in the entity registry."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        ceiling_fan("fan-name"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["light.fan_name"]
    assert entity.unique_id == "test-hub-id_test-device-id"


async def test_fan_up_light_entity_registry(hass: HomeAssistant) -> None:
    """Tests that fan with up light devices are registered in the entity registry."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        up_light_ceiling_fan("fan-name"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["light.fan_name_up_light"]
    assert entity.unique_id == "test-hub-id_test-device-id_up_light"


async def test_fan_down_light_entity_registry(hass: HomeAssistant) -> None:
    """Tests that fan with down light devices are registered in the entity registry."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        down_light_ceiling_fan("fan-name"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["light.fan_name_down_light"]
    assert entity.unique_id == "test-hub-id_test-device-id_down_light"


async def test_fireplace_entity_registry(hass: HomeAssistant) -> None:
    """Tests that flame fireplace devices are registered in the entity registry."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        fireplace("fireplace-name"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["light.fireplace_name"]
    assert entity.unique_id == "test-hub-id_test-device-id"


async def test_fireplace_with_light_entity_registry(hass: HomeAssistant) -> None:
    """Tests that flame+light devices are registered in the entity registry."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        fireplace_with_light("fireplace-name"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    registry: EntityRegistry = er.async_get(hass)
    entity_flame = registry.entities["light.fireplace_name"]
    assert entity_flame.unique_id == "test-hub-id_test-device-id"
    entity_light = registry.entities["light.fireplace_name_light"]
    assert entity_light.unique_id == "test-hub-id_test-device-id_light"


async def test_light_entity_registry(hass: HomeAssistant) -> None:
    """Tests lights are registered in the entity registry."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light("light-name"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["light.light_name"]
    assert entity.unique_id == "test-hub-id_test-device-id"


async def test_sbb_trust_state(hass: HomeAssistant) -> None:
    """Assumed state should be False if device is a Smart by Bond."""
    version = {
        "model": "MR123A",
        "bondid": "KXXX12345",
    }
    await setup_platform(
        hass, LIGHT_DOMAIN, ceiling_fan("name-1"), bond_version=version, bridge={}
    )

    device = hass.states.get("light.name_1")
    assert device.attributes.get(ATTR_ASSUMED_STATE) is not True


async def test_trust_state_not_specified(hass: HomeAssistant) -> None:
    """Assumed state should be True if Trust State is not specified."""
    await setup_platform(hass, LIGHT_DOMAIN, ceiling_fan("name-1"))

    device = hass.states.get("light.name_1")
    assert device.attributes.get(ATTR_ASSUMED_STATE) is True


async def test_trust_state(hass: HomeAssistant) -> None:
    """Assumed state should be True if Trust State is False."""
    await setup_platform(
        hass, LIGHT_DOMAIN, ceiling_fan("name-1"), props={"trust_state": False}
    )

    device = hass.states.get("light.name_1")
    assert device.attributes.get(ATTR_ASSUMED_STATE) is True


async def test_no_trust_state(hass: HomeAssistant) -> None:
    """Assumed state should be False if Trust State is True."""
    await setup_platform(
        hass, LIGHT_DOMAIN, ceiling_fan("name-1"), props={"trust_state": True}
    )
    device = hass.states.get("light.name_1")
    assert device.attributes.get(ATTR_ASSUMED_STATE) is not True


async def test_light_set_brightness_belief_full(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief function of a light delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with(
        "test-device-id", Action.set_brightness_belief(brightness=100)
    )


async def test_light_set_brightness_belief_api_error(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief throws HomeAssistantError in the event of an api error."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light("name-1"),
        bond_device_id="test-device-id",
    )

    with pytest.raises(
        HomeAssistantError
    ), patch_bond_action_returns_clientresponseerror(), patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_fp_light_set_brightness_belief_full(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief function of a light delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        fireplace_with_light_supports_brightness("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with(
        "test-device-id", Action.set_brightness_belief(brightness=100)
    )


async def test_fp_light_set_brightness_belief_api_error(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief throws HomeAssistantError in the event of an api error."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        fireplace_with_light_supports_brightness("name-1"),
        bond_device_id="test-device-id",
    )

    with pytest.raises(
        HomeAssistantError
    ), patch_bond_action_returns_clientresponseerror(), patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_light_set_brightness_belief_brightness_not_supported(
    hass: HomeAssistant,
) -> None:
    """Tests that the set brightness belief function of a light that doesn't support setting brightness returns an error."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light_no_brightness("name-1"),
        bond_device_id="test-device-id",
    )

    with pytest.raises(HomeAssistantError), patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_light_set_brightness_belief_zero(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief function of a light delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 0},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with(
        "test-device-id", Action.set_light_state_belief(False)
    )


async def test_fp_light_set_brightness_belief_zero(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief function of a light delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        fireplace_with_light_supports_brightness("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 0},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with(
        "test-device-id", Action.set_power_state_belief(False)
    )


async def test_light_set_power_belief(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief function of a light delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_POWER_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_POWER_STATE: False},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with(
        "test-device-id", Action.set_light_state_belief(False)
    )


async def test_light_set_power_belief_api_error(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief function of a light throws HomeAssistantError in the event of an api error."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light("name-1"),
        bond_device_id="test-device-id",
    )

    with pytest.raises(
        HomeAssistantError
    ), patch_bond_action_returns_clientresponseerror(), patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_POWER_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_POWER_STATE: False},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_fp_light_set_power_belief(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief function of a light delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        fireplace_with_light("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_POWER_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_POWER_STATE: False},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with(
        "test-device-id", Action.set_power_state_belief(False)
    )


async def test_fp_light_set_power_belief_api_error(hass: HomeAssistant) -> None:
    """Tests that the set brightness belief function of a light throws HomeAssistantError in the event of an api error."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        fireplace_with_light("name-1"),
        bond_device_id="test-device-id",
    )

    with pytest.raises(
        HomeAssistantError
    ), patch_bond_action_returns_clientresponseerror(), patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_POWER_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_POWER_STATE: False},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_fp_light_set_brightness_belief_brightness_not_supported(
    hass: HomeAssistant,
) -> None:
    """Tests that the set brightness belief function of a fireplace light that doesn't support setting brightness returns an error."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        fireplace_with_light("name-1"),
        bond_device_id="test-device-id",
    )

    with pytest.raises(HomeAssistantError), patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_light_start_increasing_brightness(hass: HomeAssistant) -> None:
    """Tests a light that can only increase or decrease brightness delegates to API can start increasing brightness."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light_brightness_increase_decrease_only("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_INCREASING_BRIGHTNESS,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with(
        "test-device-id", Action(Action.START_INCREASING_BRIGHTNESS)
    )


async def test_light_start_increasing_brightness_missing_service(
    hass: HomeAssistant,
) -> None:
    """Tests a light does not have start increasing brightness throws."""
    await setup_platform(
        hass, LIGHT_DOMAIN, light("name-1"), bond_device_id="test-device-id"
    )

    with pytest.raises(HomeAssistantError), patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_INCREASING_BRIGHTNESS,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_light_start_decreasing_brightness(hass: HomeAssistant) -> None:
    """Tests a light that can only increase or decrease brightness delegates to API can start decreasing brightness."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light_brightness_increase_decrease_only("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_DECREASING_BRIGHTNESS,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with(
        "test-device-id", Action(Action.START_DECREASING_BRIGHTNESS)
    )


async def test_light_start_decreasing_brightness_missing_service(
    hass: HomeAssistant,
) -> None:
    """Tests a light does not have start decreasing brightness throws."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light("name-1"),
        bond_device_id="test-device-id",
    )

    with pytest.raises(HomeAssistantError), patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_DECREASING_BRIGHTNESS,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_light_stop(hass: HomeAssistant) -> None:
    """Tests a light that can only increase or decrease brightness delegates to API can stop."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light_brightness_increase_decrease_only("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_bond_action, patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_bond_action.assert_called_once_with("test-device-id", Action(Action.STOP))


async def test_light_stop_missing_service(
    hass: HomeAssistant,
) -> None:
    """Tests a light does not have stop throws."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        light("name-1"),
        bond_device_id="test-device-id",
    )

    with pytest.raises(HomeAssistantError), patch_bond_device_state():
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_turn_on_light(hass: HomeAssistant) -> None:
    """Tests that turn on command delegates to API."""
    await setup_platform(
        hass, LIGHT_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_light_on, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_light_on.assert_called_once_with("test-device-id", Action.turn_light_on())


async def test_turn_off_light(hass: HomeAssistant) -> None:
    """Tests that turn off command delegates to API."""
    await setup_platform(
        hass, LIGHT_DOMAIN, ceiling_fan("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_light_off, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_light_off.assert_called_once_with(
        "test-device-id", Action.turn_light_off()
    )


async def test_brightness_support(hass: HomeAssistant) -> None:
    """Tests that a dimmable light should support the brightness feature."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        dimmable_ceiling_fan("name-1"),
        bond_device_id="test-device-id",
    )

    state = hass.states.get("light.name_1")
    assert state.state == "off"
    assert ATTR_COLOR_MODE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    with patch_bond_device_state(return_value={"light": 1, "brightness": 50}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    state = hass.states.get("light.name_1")
    assert state.state == "on"
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.BRIGHTNESS
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.BRIGHTNESS]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0


async def test_brightness_not_supported(hass: HomeAssistant) -> None:
    """Tests that a non-dimmable light should not support the brightness feature."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        ceiling_fan("name-1"),
        bond_device_id="test-device-id",
    )

    state = hass.states.get("light.name_1")
    assert state.state == "off"
    assert ATTR_COLOR_MODE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    with patch_bond_device_state(return_value={"light": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    state = hass.states.get("light.name_1")
    assert state.state == "on"
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.ONOFF
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0


async def test_turn_on_light_with_brightness(hass: HomeAssistant) -> None:
    """Tests that turn on command, on a dimmable light, delegates to API and parses brightness."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        dimmable_ceiling_fan("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_set_brightness, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 128},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_set_brightness.assert_called_once_with(
        "test-device-id", Action(Action.SET_BRIGHTNESS, 50)
    )


async def test_turn_on_up_light(hass: HomeAssistant) -> None:
    """Tests that turn on command, on an up light, delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        up_light_ceiling_fan("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_turn_on, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.name_1_up_light"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_on.assert_called_once_with(
        "test-device-id", Action(Action.TURN_UP_LIGHT_ON)
    )


async def test_turn_off_up_light(hass: HomeAssistant) -> None:
    """Tests that turn off command, on an up light, delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        up_light_ceiling_fan("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_turn_off, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.name_1_up_light"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_off.assert_called_once_with(
        "test-device-id", Action(Action.TURN_UP_LIGHT_OFF)
    )


async def test_turn_on_down_light(hass: HomeAssistant) -> None:
    """Tests that turn on command, on a down light, delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        down_light_ceiling_fan("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_turn_on, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.name_1_down_light"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_on.assert_called_once_with(
        "test-device-id", Action(Action.TURN_DOWN_LIGHT_ON)
    )


async def test_turn_off_down_light(hass: HomeAssistant) -> None:
    """Tests that turn off command, on a down light, delegates to API."""
    await setup_platform(
        hass,
        LIGHT_DOMAIN,
        down_light_ceiling_fan("name-1"),
        bond_device_id="test-device-id",
    )

    with patch_bond_action() as mock_turn_off, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.name_1_down_light"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_off.assert_called_once_with(
        "test-device-id", Action(Action.TURN_DOWN_LIGHT_OFF)
    )


async def test_update_reports_light_is_on(hass: HomeAssistant) -> None:
    """Tests that update command sets correct state when Bond API reports the light is on."""
    await setup_platform(hass, LIGHT_DOMAIN, ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"light": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1").state == "on"


async def test_update_reports_light_is_off(hass: HomeAssistant) -> None:
    """Tests that update command sets correct state when Bond API reports the light is off."""
    await setup_platform(hass, LIGHT_DOMAIN, ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"light": 0}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1").state == "off"


async def test_update_reports_up_light_is_on(hass: HomeAssistant) -> None:
    """Tests that update command sets correct state when Bond API reports the up light is on."""
    await setup_platform(hass, LIGHT_DOMAIN, up_light_ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"up_light": 1, "light": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1_up_light").state == "on"


async def test_update_reports_up_light_is_off(hass: HomeAssistant) -> None:
    """Tests that update command sets correct state when Bond API reports the up light is off."""
    await setup_platform(hass, LIGHT_DOMAIN, up_light_ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"up_light": 0, "light": 0}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1_up_light").state == "off"


async def test_update_reports_down_light_is_on(hass: HomeAssistant) -> None:
    """Tests that update command sets correct state when Bond API reports the down light is on."""
    await setup_platform(hass, LIGHT_DOMAIN, down_light_ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"down_light": 1, "light": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1_down_light").state == "on"


async def test_update_reports_down_light_is_off(hass: HomeAssistant) -> None:
    """Tests that update command sets correct state when Bond API reports the down light is off."""
    await setup_platform(hass, LIGHT_DOMAIN, down_light_ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"down_light": 0, "light": 0}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1_down_light").state == "off"


async def test_turn_on_fireplace_with_brightness(hass: HomeAssistant) -> None:
    """Tests that turn on command delegates to set flame API."""
    await setup_platform(
        hass, LIGHT_DOMAIN, fireplace("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_set_flame, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.name_1", ATTR_BRIGHTNESS: 128},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_set_flame.assert_called_once_with("test-device-id", Action.set_flame(50))


async def test_turn_on_fireplace_without_brightness(hass: HomeAssistant) -> None:
    """Tests that turn on command delegates to turn on API."""
    await setup_platform(
        hass, LIGHT_DOMAIN, fireplace("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_on, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_on.assert_called_once_with("test-device-id", Action.turn_on())


async def test_turn_off_fireplace(hass: HomeAssistant) -> None:
    """Tests that turn off command delegates to API."""
    await setup_platform(
        hass, LIGHT_DOMAIN, fireplace("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_turn_off, patch_bond_device_state():
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_turn_off.assert_called_once_with("test-device-id", Action.turn_off())


async def test_flame_converted_to_brightness(hass: HomeAssistant) -> None:
    """Tests that reported flame level (0..100) converted to HA brightness (0...255)."""
    await setup_platform(hass, LIGHT_DOMAIN, fireplace("name-1"))

    with patch_bond_device_state(return_value={"power": 1, "flame": 50}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1").attributes[ATTR_BRIGHTNESS] == 128


async def test_light_available(hass: HomeAssistant) -> None:
    """Tests that available state is updated based on API errors."""
    await help_test_entity_available(
        hass, LIGHT_DOMAIN, ceiling_fan("name-1"), "light.name_1"
    )


async def test_parse_brightness(hass: HomeAssistant) -> None:
    """Tests that reported brightness level (0..100) converted to HA brightness (0...255)."""
    await setup_platform(hass, LIGHT_DOMAIN, dimmable_ceiling_fan("name-1"))

    with patch_bond_device_state(return_value={"light": 1, "brightness": 50}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("light.name_1").attributes[ATTR_BRIGHTNESS] == 128
