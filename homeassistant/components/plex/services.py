"""Services for the Plex integration."""
import json
import logging

from plexapi.exceptions import BadRequest, NotFound
import voluptuous as vol

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
)
from homeassistant.components.sonos import DOMAIN as SONOS_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import entity_sources

from .const import (
    DOMAIN,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    SERVERS,
    SERVICE_PLAY_ON_OTHER,
    SERVICE_PLAY_ON_SONOS,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SCAN_CLIENTS,
)

REFRESH_LIBRARY_SCHEMA = vol.Schema(
    {vol.Optional("server_name"): str, vol.Required("library_name"): str}
)
PLAY_ON_OTHER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_MEDIA_CONTENT_ID): str,
        vol.Optional(ATTR_MEDIA_CONTENT_TYPE): str,
    }
)
PLAY_ON_SONOS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_MEDIA_CONTENT_ID): str,
        vol.Optional(ATTR_MEDIA_CONTENT_TYPE): vol.In("music"),
    }
)

_LOGGER = logging.getLogger(__package__)


async def async_setup_services(hass):
    """Set up services for the Plex component."""

    async def async_refresh_library_service(service_call):
        await hass.async_add_executor_job(refresh_library, hass, service_call)

    async def async_scan_clients_service(_):
        _LOGGER.debug("Scanning for new Plex clients")
        for server_id in hass.data[DOMAIN][SERVERS]:
            async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))

    async def async_play_on_other_service(service_call):
        await hass.async_add_executor_job(play_media_on_other, hass, service_call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        async_refresh_library_service,
        schema=REFRESH_LIBRARY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SCAN_CLIENTS, async_scan_clients_service
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_ON_OTHER,
        async_play_on_other_service,
        schema=PLAY_ON_OTHER_SCHEMA,
    )

    async def async_play_on_sonos_service(service_call):
        _LOGGER.warning(
            "Service `plex.play_on_sonos` is deprecated, please use `plex.play_media`"
        )
        await hass.async_add_executor_job(play_media_on_other, hass, service_call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_ON_SONOS,
        async_play_on_sonos_service,
        schema=PLAY_ON_SONOS_SCHEMA,
    )

    return True


def refresh_library(hass, service_call):
    """Scan a Plex library for new and updated media."""
    plex_server_name = service_call.data.get("server_name")
    library_name = service_call.data["library_name"]

    plex_server = get_plex_server(hass, plex_server_name)
    if not plex_server:
        return

    try:
        library = plex_server.library.section(title=library_name)
    except NotFound:
        _LOGGER.error(
            "Library with name '%s' not found in %s",
            library_name,
            [x.title for x in plex_server.library.sections()],
        )
        return

    _LOGGER.debug("Scanning %s for new and updated media", library_name)
    library.update()


def get_plex_server(hass, plex_server_name=None):
    """Retrieve a configured Plex server by name."""
    plex_servers = hass.data[DOMAIN][SERVERS].values()

    if plex_server_name:
        plex_server = next(
            (x for x in plex_servers if x.friendly_name == plex_server_name), None
        )
        if not plex_server:
            _LOGGER.error(
                "Requested Plex server '%s' not found in %s",
                plex_server_name,
                [x.friendly_name for x in plex_servers],
            )
            return None
    elif len(plex_servers) == 1:
        plex_server = next(iter(plex_servers))
    else:
        _LOGGER.warning(
            "Multiple Plex servers configured and no selection made: %s",
            [x.friendly_name for x in plex_servers],
        )
        return None

    return plex_server


def lookup_plex_media(hass, content_type, content_id):
    """Look up Plex media using media_player.play_media service payloads."""
    content = json.loads(content_id)

    if isinstance(content, int):
        content = {"plex_key": content}
        content_type = DOMAIN

    plex_server_name = content.pop("plex_server", None)
    shuffle = content.pop("shuffle", 0)

    plex_server = get_plex_server(hass, plex_server_name=plex_server_name)
    if not plex_server:
        return (None, None)

    media = plex_server.lookup_media(content_type, **content)
    if media is None:
        _LOGGER.error("Media could not be found: %s", content)
        return (None, None)

    playqueue = plex_server.create_playqueue(media, shuffle=shuffle)
    return (playqueue, plex_server)


def play_media_on_other(hass, service_call):
    """Play Plex media on a capable non-Plex media_player."""
    entity_id = service_call.data[ATTR_ENTITY_ID]
    content_id = service_call.data[ATTR_MEDIA_CONTENT_ID]
    content_type = service_call.data[ATTR_MEDIA_CONTENT_TYPE]

    entity_source = entity_sources(hass).get(entity_id)
    if not entity_source:
        _LOGGER.warning("Entity not found: %s", entity_id)
        return

    domain = entity_source[CONF_DOMAIN]
    if domain not in [SONOS_DOMAIN]:
        _LOGGER.error("%s is not a supported integration [%s]", domain, entity_id)
        return

    media, plex_server = lookup_plex_media(hass, content_type, content_id)
    if media is None:
        return

    if domain == SONOS_DOMAIN:
        play_media_on_sonos(hass, entity_id, media, plex_server)


def play_media_on_sonos(hass, entity_id, media, plex_server):
    """Play Plex media on a linked Sonos device."""
    sonos = hass.components.sonos
    try:
        sonos_name = sonos.get_coordinator_name(entity_id)
    except HomeAssistantError as err:
        _LOGGER.error("Cannot get Sonos device: %s", err)
        return

    try:
        sonos_speaker = plex_server.account.sonos_speaker(sonos_name)
    except BadRequest:
        _LOGGER.error(
            "Plex server '%s' does not have an active Plex Pass",
            plex_server.friendly_name,
        )
        return

    if sonos_speaker is None:
        _LOGGER.error(
            "Sonos speaker '%s' could not be found on this Plex account", sonos_name
        )
        return

    _LOGGER.debug("Attempting to play '%s' on %s", media, sonos_speaker)
    sonos_speaker.playMedia(media)
