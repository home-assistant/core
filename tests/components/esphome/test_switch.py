"""Test ESPHome switches."""

from unittest.mock import call

from aioesphomeapi import APIClient, SwitchInfo, SwitchState

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import MockGenericDeviceEntryType


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
            unique_id="my_switch",
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
    state = hass.states.get("switch.test_myswitch")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_myswitch"},
        blocking=True,
    )
    mock_client.switch_command.assert_has_calls([call(1, True)])

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_myswitch"},
        blocking=True,
    )
    mock_client.switch_command.assert_has_calls([call(1, False)])
