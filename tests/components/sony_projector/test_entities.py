"""Tests for Sony Projector entities beyond the media player."""

from __future__ import annotations

from homeassistant.components.sony_projector.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_select_entities(
    hass: HomeAssistant,
    init_integration,
    mock_projector_client,
    mock_projector_state,
) -> None:
    """Verify select entities reflect the coordinator state and send commands."""

    ent_reg = er.async_get(hass)
    aspect_entity_id = ent_reg.async_get_entity_id(
        "select", DOMAIN, f"{mock_projector_state.serial}-aspect_ratio"
    )
    picture_entity_id = ent_reg.async_get_entity_id(
        "select", DOMAIN, f"{mock_projector_state.serial}-picture_mode"
    )

    assert hass.states.get(aspect_entity_id).state == mock_projector_state.aspect_ratio
    assert hass.states.get(picture_entity_id).state == mock_projector_state.picture_mode

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": aspect_entity_id, "option": "SQUEEZE"},
        blocking=True,
    )
    mock_projector_client.async_set_aspect_ratio.assert_called_with("SQUEEZE")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": picture_entity_id, "option": "GAME"},
        blocking=True,
    )
    mock_projector_client.async_set_picture_mode.assert_called_with("GAME")


async def test_button_and_sensors(
    hass: HomeAssistant,
    init_integration,
    mock_projector_client,
    mock_projector_state,
) -> None:
    """Verify button and sensors are registered."""

    ent_reg = er.async_get(hass)
    button_entity_id = ent_reg.async_get_entity_id(
        "button", DOMAIN, f"{mock_projector_state.serial}-picture_mute"
    )
    lamp_sensor_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_projector_state.serial}-lamp_hours"
    )
    model_sensor_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_projector_state.serial}-model"
    )
    serial_sensor_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_projector_state.serial}-serial"
    )

    assert hass.states.get(lamp_sensor_id).state == str(mock_projector_state.lamp_hours)
    assert hass.states.get(model_sensor_id).state == mock_projector_state.model
    assert hass.states.get(serial_sensor_id).state == mock_projector_state.serial

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": button_entity_id},
        blocking=True,
    )
    mock_projector_client.async_toggle_picture_mute.assert_called_once()
