"""Test DoorBird buttons."""

from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.components.button import DOMAIN, SERVICE_PRESS
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import MockDoorbirdEntry


async def test_relay_button(
    hass: HomeAssistant,
    doorbird_mocker: Callable[[], Coroutine[Any, Any, MockDoorbirdEntry]],
) -> None:
    """Test pressing a relay button."""
    doorbird_entry = await doorbird_mocker()
    relay_1_entity_id = "button.mydoorbird_relay_1"
    button_1 = hass.states.get(relay_1_entity_id)
    assert button_1.state == STATE_UNKNOWN
    await hass.services.async_call(
        DOMAIN, SERVICE_PRESS, {"entity_id": relay_1_entity_id}, blocking=True
    )
    button_1 = hass.states.get(relay_1_entity_id)
    assert button_1.state != STATE_UNKNOWN
    api = doorbird_entry.api
    assert api.energize_relay.call_count == 1


async def test_ir_button(
    hass: HomeAssistant,
    doorbird_mocker: Callable[[], Coroutine[Any, Any, MockDoorbirdEntry]],
) -> None:
    """Test pressing the IR button."""
    doorbird_entry = await doorbird_mocker()
    ir_entity_id = "button.mydoorbird_ir"
    ir_button = hass.states.get(ir_entity_id)
    assert ir_button.state == STATE_UNKNOWN
    await hass.services.async_call(
        DOMAIN, SERVICE_PRESS, {"entity_id": ir_entity_id}, blocking=True
    )
    ir_button = hass.states.get(ir_entity_id)
    assert ir_button.state != STATE_UNKNOWN
    api = doorbird_entry.api
    assert api.turn_light_on.call_count == 1


async def test_reset_favorites_button(
    hass: HomeAssistant,
    doorbird_mocker: Callable[[], Coroutine[Any, Any, MockDoorbirdEntry]],
) -> None:
    """Test pressing the reset favorites button."""
    doorbird_entry = await doorbird_mocker()
    reset_entity_id = "button.mydoorbird_reset_favorites"
    reset_button = hass.states.get(reset_entity_id)
    assert reset_button.state == STATE_UNKNOWN
    await hass.services.async_call(
        DOMAIN, SERVICE_PRESS, {"entity_id": reset_entity_id}, blocking=True
    )
    reset_button = hass.states.get(reset_entity_id)
    assert reset_button.state != STATE_UNKNOWN
    api = doorbird_entry.api
    assert api.delete_favorite.call_count == 1
