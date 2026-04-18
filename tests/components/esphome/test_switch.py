"""Test ESPHome switches."""

from unittest.mock import call

from aioesphomeapi import APIClient, SubDeviceInfo, SwitchInfo, SwitchState

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDeviceType, MockGenericDeviceEntryType


async def test_switch_generic_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic switch entity."""
    entity_info = [
        SwitchInfo(
            object_id="myswitch",
            key=1,
            name="my switch",
        )
    ]
    states = [SwitchState(key=1, state=True)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("switch.test_my_switch")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_my_switch"},
        blocking=True,
    )
    mock_client.switch_command.assert_has_calls([call(1, True, device_id=0)])

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_my_switch"},
        blocking=True,
    )
    mock_client.switch_command.assert_has_calls([call(1, False, device_id=0)])


async def test_switch_sub_device_non_zero_device_id(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test switch on sub-device with non-zero device_id passes through to API."""
    # Create sub-device
    sub_devices = [
        SubDeviceInfo(device_id=11111111, name="Sub Device", area_id=0),
    ]
    device_info = {
        "name": "test",
        "devices": sub_devices,
    }
    # Create switches on both main device and sub-device
    entity_info = [
        SwitchInfo(
            object_id="main_switch",
            key=1,
            name="Main Switch",
            device_id=0,  # Main device
        ),
        SwitchInfo(
            object_id="sub_switch",
            key=2,
            name="Sub Switch",
            device_id=11111111,  # Sub-device
        ),
    ]
    # States for both switches
    states = [
        SwitchState(key=1, state=True, device_id=0),
        SwitchState(key=2, state=False, device_id=11111111),
    ]
    await mock_esphome_device(
        mock_client=mock_client,
        device_info=device_info,
        entity_info=entity_info,
        states=states,
    )

    # Verify both entities exist with correct states
    main_state = hass.states.get("switch.test_main_switch")
    assert main_state is not None
    assert main_state.state == STATE_ON

    sub_state = hass.states.get("switch.sub_device_sub_switch")
    assert sub_state is not None
    assert sub_state.state == STATE_OFF

    # Test turning on the sub-device switch - should pass device_id=11111111
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.sub_device_sub_switch"},
        blocking=True,
    )
    mock_client.switch_command.assert_has_calls([call(2, True, device_id=11111111)])
    mock_client.switch_command.reset_mock()

    # Test turning off the sub-device switch - should pass device_id=11111111
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.sub_device_sub_switch"},
        blocking=True,
    )
    mock_client.switch_command.assert_has_calls([call(2, False, device_id=11111111)])
    mock_client.switch_command.reset_mock()

    # Test main device switch still uses device_id=0
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_main_switch"},
        blocking=True,
    )
    mock_client.switch_command.assert_has_calls([call(1, True, device_id=0)])
    mock_client.switch_command.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_main_switch"},
        blocking=True,
    )
    mock_client.switch_command.assert_has_calls([call(1, False, device_id=0)])
