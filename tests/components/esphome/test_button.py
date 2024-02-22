"""Test ESPHome buttones."""


from unittest.mock import call

from aioesphomeapi import APIClient, ButtonInfo

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant


async def test_button_generic_entity(
    hass: HomeAssistant, mock_client: APIClient, mock_esphome_device
) -> None:
    """Test a generic button entity."""
    entity_info = [
        ButtonInfo(
            object_id="mybutton",
            key=1,
            name="my button",
            unique_id="my_button",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("button.test_mybutton")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_mybutton"},
        blocking=True,
    )
    mock_client.button_command.assert_has_calls([call(1)])
    state = hass.states.get("button.test_mybutton")
    assert state is not None
    assert state.state != STATE_UNKNOWN

    await mock_device.mock_disconnect(False)
    state = hass.states.get("button.test_mybutton")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
