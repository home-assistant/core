"""Tests for the Sony Projector media player entity."""

from __future__ import annotations

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.components.sony_projector.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_media_player_state(
    hass: HomeAssistant,
    init_integration,
    mock_projector_client,
    mock_projector_state,
) -> None:
    """Test media player state and commands."""

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        "media_player", DOMAIN, f"{mock_projector_state.serial}-media_player"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == MediaPlayerState.ON
    assert state.attributes["source"] == mock_projector_state.current_input
    assert state.attributes["source_list"] == mock_projector_state.inputs

    await hass.services.async_call(
        "media_player", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    mock_projector_client.async_set_power.assert_called_with(False)

    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": entity_id, "source": "HDMI 2"},
        blocking=True,
    )
    mock_projector_client.async_set_input.assert_called_with("HDMI 2")
