"""Test ESPHome buttones."""

from unittest.mock import call

from aioesphomeapi import APIClient, ButtonInfo

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MockESPHomeDeviceType, reconnect_with_updated_entity_info


async def test_button_generic_entity(
    hass: HomeAssistant, mock_client: APIClient, mock_esphome_device
) -> None:
    """Test a generic button entity."""
    entity_info = [
        ButtonInfo(
            object_id="mybutton",
            key=1,
            name="my button",
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
    state = hass.states.get("button.test_my_button")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: "button.test_my_button"},
        blocking=True,
    )
    mock_client.button_command.assert_has_calls([call(1, device_id=0)])
    state = hass.states.get("button.test_my_button")
    assert state is not None
    assert state.state != STATE_UNKNOWN

    await mock_device.mock_disconnect(False)
    state = hass.states.get("button.test_my_button")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_button_rename_on_reconnect(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """A reconnect updates a button's display name while preserving its entity ID."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[ButtonInfo(key=1, name="Open blind")],
    )
    entity_id = "button.test_open_blind"
    before = entity_registry.async_get(entity_id)
    assert before is not None
    assert before.original_name == "Open blind"

    await reconnect_with_updated_entity_info(
        hass, device, [ButtonInfo(key=1, name="Open shade")]
    )

    after = entity_registry.async_get(entity_id)
    assert after is not None
    assert after.id == before.id
    assert after.original_name == "Open shade"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Test Open shade"
