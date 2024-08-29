"""Assist satellite Websocket API."""

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ERR_NOT_SUPPORTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_component import EntityComponent

from .const import DOMAIN
from .entity import AssistSatelliteEntity
from .models import AssistSatelliteEntityFeature


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_intercept_wake_word)
    websocket_api.async_register_command(hass, websocket_announce)


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "assist_satellite/intercept_wake_word",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_intercept_wake_word(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Intercept the next wake word from a satellite."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    satellite = component.get_entity(msg["entity_id"])
    if satellite is None:
        connection.send_error(msg["id"], "entity_not_found", "Entity not found")
        return

    wake_word_phrase = await satellite.async_intercept_wake_word()
    connection.send_result(msg["id"], {"wake_word_phrase": wake_word_phrase})


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "assist_satellite/announce",
        vol.Required("entity_id"): str,
        vol.Required(vol.Any("text", "media_id")): str,
    }
)
@websocket_api.async_response
async def websocket_announce(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Announce text or a media id on the satellite."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    satellite = component.get_entity(msg["entity_id"])
    if satellite is None:
        connection.send_error(msg["id"], "entity_not_found", "Entity not found")
        return

    if (satellite.supported_features is None) or (
        not (satellite.supported_features & AssistSatelliteEntityFeature.ANNOUNCE)
    ):
        connection.send_message(
            websocket_api.error_message(
                msg["id"], ERR_NOT_SUPPORTED, "Satellite does not support announcements"
            )
        )
        return

    await satellite.async_announce(msg.get("text", ""), msg.get("media_id"))
    connection.send_result(msg["id"], {})
