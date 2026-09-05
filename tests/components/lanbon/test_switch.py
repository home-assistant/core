"""Tests for LANBON switch platform."""

from unittest.mock import AsyncMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_switch_entities_only_type_switch(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Only LOIP type=switch components become switch entities."""
    states = hass.states.async_all("switch")
    assert len(states) == 1
    assert states[0].state == STATE_OFF


async def test_turn_on_off(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_lanbon_client: AsyncMock,
) -> None:
    """Test turn on and off send set_on."""
    entity_id = hass.states.async_entity_ids("switch")[0]
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    mock_lanbon_client.send_command.assert_awaited()
    args = mock_lanbon_client.send_command.await_args.args
    assert args[2] == "set_on"
    assert args[3] == {"on": True}

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert mock_lanbon_client.send_command.await_args.args[3] == {"on": False}
    assert hass.states.get(entity_id).state in {STATE_ON, STATE_OFF}
