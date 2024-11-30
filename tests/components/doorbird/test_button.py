"""Test DoorBird buttons."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import DoorbirdMockerType


async def test_relay_button(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test pressing a relay button."""
    doorbird_entry = await doorbird_mocker()
    relay_1_entity_id = "button.mydoorbird_relay_1"
    assert hass.states.get(relay_1_entity_id).state == STATE_UNKNOWN
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: relay_1_entity_id}, blocking=True
    )
    assert hass.states.get(relay_1_entity_id).state != STATE_UNKNOWN
    assert doorbird_entry.api.energize_relay.call_count == 1


async def test_ir_button(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test pressing the IR button."""
    doorbird_entry = await doorbird_mocker()
    ir_entity_id = "button.mydoorbird_ir"
    assert hass.states.get(ir_entity_id).state == STATE_UNKNOWN
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ir_entity_id}, blocking=True
    )
    assert hass.states.get(ir_entity_id).state != STATE_UNKNOWN
    assert doorbird_entry.api.turn_light_on.call_count == 1


async def test_reset_favorites_button(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test pressing the reset favorites button."""
    doorbird_entry = await doorbird_mocker()
    reset_entity_id = "button.mydoorbird_reset_favorites"
    assert hass.states.get(reset_entity_id).state == STATE_UNKNOWN
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: reset_entity_id}, blocking=True
    )
    assert hass.states.get(reset_entity_id).state != STATE_UNKNOWN
    assert doorbird_entry.api.delete_favorite.call_count == 3
