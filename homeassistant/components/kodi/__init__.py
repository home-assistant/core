"""The kodi component."""

import asyncio

import voluptuous as vol

from homeassistant.components.kodi.const import DOMAIN
from homeassistant.components.media_player.const import DOMAIN as MP_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM
from homeassistant.helpers import config_validation as cv

SERVICE_ADD_MEDIA = "add_to_playlist"
SERVICE_CALL_METHOD = "call_method"

ATTR_MEDIA_TYPE = "media_type"
ATTR_MEDIA_NAME = "media_name"
ATTR_MEDIA_ARTIST_NAME = "artist_name"
ATTR_MEDIA_ID = "media_id"
ATTR_METHOD = "method"

MEDIA_PLAYER_SCHEMA = vol.Schema({ATTR_ENTITY_ID: cv.comp_entity_ids})

KODI_ADD_MEDIA_SCHEMA = MEDIA_PLAYER_SCHEMA.extend(
    {
        vol.Required(ATTR_MEDIA_TYPE): cv.string,
        vol.Optional(ATTR_MEDIA_ID): cv.string,
        vol.Optional(ATTR_MEDIA_NAME): cv.string,
        vol.Optional(ATTR_MEDIA_ARTIST_NAME): cv.string,
    }
)
KODI_CALL_METHOD_SCHEMA = MEDIA_PLAYER_SCHEMA.extend(
    {vol.Required(ATTR_METHOD): cv.string}, extra=vol.ALLOW_EXTRA
)

SERVICE_TO_METHOD = {
    SERVICE_ADD_MEDIA: {
        "method": "async_add_media_to_playlist",
        "schema": KODI_ADD_MEDIA_SCHEMA,
    },
    SERVICE_CALL_METHOD: {
        "method": "async_call_method",
        "schema": KODI_CALL_METHOD_SCHEMA,
    },
}


async def async_setup(hass, config):
    """Set up the Kodi integration."""
    if any((CONF_PLATFORM, DOMAIN) in cfg.items() for cfg in config.get(MP_DOMAIN, [])):
        # Register the Kodi media_player services
        async def async_service_handler(service):
            """Map services to methods on MediaPlayerDevice."""
            method = SERVICE_TO_METHOD.get(service.service)
            if not method:
                return

            params = {
                key: value for key, value in service.data.items() if key != "entity_id"
            }
            entity_ids = service.data.get("entity_id")
            if entity_ids:
                target_players = [
                    player
                    for player in hass.data[DOMAIN].values()
                    if player.entity_id in entity_ids
                ]
            else:
                target_players = hass.data[DOMAIN].values()

            update_tasks = []
            for player in target_players:
                await getattr(player, method["method"])(**params)

            for player in target_players:
                if player.should_poll:
                    update_coro = player.async_update_ha_state(True)
                    update_tasks.append(update_coro)

            if update_tasks:
                await asyncio.wait(update_tasks)

        for service in SERVICE_TO_METHOD:
            schema = SERVICE_TO_METHOD[service]["schema"]
            hass.services.async_register(
                DOMAIN, service, async_service_handler, schema=schema
            )

    # Return boolean to indicate that initialization was successful.
    return True
