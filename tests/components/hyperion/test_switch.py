"""Tests for the Hyperion integration."""
from unittest.mock import AsyncMock, call, patch

from hyperion.const import (
    KEY_COMPONENT,
    KEY_COMPONENTID_ALL,
    KEY_COMPONENTID_BLACKBORDER,
    KEY_COMPONENTID_BOBLIGHTSERVER,
    KEY_COMPONENTID_FORWARDER,
    KEY_COMPONENTID_GRABBER,
    KEY_COMPONENTID_LEDDEVICE,
    KEY_COMPONENTID_SMOOTHING,
    KEY_COMPONENTID_V4L,
    KEY_COMPONENTSTATE,
    KEY_STATE,
)

from homeassistant.components.hyperion.const import COMPONENT_TO_NAME
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify

from . import call_registered_callback, create_mock_client, setup_test_config_entry

TEST_COMPONENTS = [
    {"enabled": True, "name": "ALL"},
    {"enabled": True, "name": "SMOOTHING"},
    {"enabled": True, "name": "BLACKBORDER"},
    {"enabled": False, "name": "FORWARDER"},
    {"enabled": False, "name": "BOBLIGHTSERVER"},
    {"enabled": False, "name": "GRABBER"},
    {"enabled": False, "name": "V4L"},
    {"enabled": True, "name": "LEDDEVICE"},
]

TEST_SWITCH_COMPONENT_BASE_ENTITY_ID = "switch.test_instance_1_component"
TEST_SWITCH_COMPONENT_ALL_ENTITY_ID = f"{TEST_SWITCH_COMPONENT_BASE_ENTITY_ID}_all"


async def test_switch_turn_on_off(hass: HomeAssistantType) -> None:
    """Test turning the light on."""
    client = create_mock_client()
    client.async_send_set_component = AsyncMock(return_value=True)
    client.components = TEST_COMPONENTS

    # Setup component switch.
    with patch(
        "homeassistant.components.hyperion.switch.HyperionComponentSwitch.entity_registry_enabled_default"
    ) as enabled_by_default_mock:
        enabled_by_default_mock.return_value = True
        await setup_test_config_entry(hass, hyperion_client=client)

    # Verify switch is on (as per TEST_COMPONENTS above).
    entity_state = hass.states.get(TEST_SWITCH_COMPONENT_ALL_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"

    # Turn switch off.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_SWITCH_COMPONENT_ALL_ENTITY_ID},
        blocking=True,
    )

    # Verify correct parameters are passed to the library.
    assert client.async_send_set_component.call_args == call(
        **{KEY_COMPONENTSTATE: {KEY_COMPONENT: KEY_COMPONENTID_ALL, KEY_STATE: False}}
    )

    client.components[0] = {
        "enabled": False,
        "name": "ALL",
    }
    call_registered_callback(client, "components-update")

    # Verify the switch turns off.
    entity_state = hass.states.get(TEST_SWITCH_COMPONENT_ALL_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "off"

    # Turn switch on.
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SWITCH_COMPONENT_ALL_ENTITY_ID},
        blocking=True,
    )

    # Verify correct parameters are passed to the library.
    assert client.async_send_set_component.call_args == call(
        **{KEY_COMPONENTSTATE: {KEY_COMPONENT: KEY_COMPONENTID_ALL, KEY_STATE: True}}
    )

    client.components[0] = {
        "enabled": True,
        "name": "ALL",
    }
    call_registered_callback(client, "components-update")

    # Verify the switch turns on.
    entity_state = hass.states.get(TEST_SWITCH_COMPONENT_ALL_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "on"


async def test_switch_has_correct_entities(hass: HomeAssistantType) -> None:
    """Test that the correct switch entities are created."""
    client = create_mock_client()
    client.components = TEST_COMPONENTS

    # Setup component switch.
    with patch(
        "homeassistant.components.hyperion.switch.HyperionComponentSwitch.entity_registry_enabled_default"
    ) as enabled_by_default_mock:
        enabled_by_default_mock.return_value = True
        await setup_test_config_entry(hass, hyperion_client=client)

    entity_state = hass.states.get(TEST_SWITCH_COMPONENT_ALL_ENTITY_ID)

    for component in (
        KEY_COMPONENTID_ALL,
        KEY_COMPONENTID_SMOOTHING,
        KEY_COMPONENTID_BLACKBORDER,
        KEY_COMPONENTID_FORWARDER,
        KEY_COMPONENTID_BOBLIGHTSERVER,
        KEY_COMPONENTID_GRABBER,
        KEY_COMPONENTID_LEDDEVICE,
        KEY_COMPONENTID_V4L,
    ):
        entity_id = (
            TEST_SWITCH_COMPONENT_BASE_ENTITY_ID
            + "_"
            + slugify(COMPONENT_TO_NAME[component])
        )
        entity_state = hass.states.get(entity_id)
        assert entity_state, f"Couldn't find entity: {entity_id}"
