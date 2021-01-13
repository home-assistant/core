"""Services for the Plex integration."""
import json
import logging

from plexapi.exceptions import NotFound
import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    SERVERS,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SCAN_CLIENTS,
)

REFRESH_LIBRARY_SCHEMA = vol.Schema(
    {vol.Optional("server_name"): str, vol.Required("library_name"): str}
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

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        async_refresh_library_service,
        schema=REFRESH_LIBRARY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SCAN_CLIENTS, async_scan_clients_service
    )

    return True


def refresh_library(hass, service_call):
    """Scan a Plex library for new and updated media."""
    plex_server_name = service_call.data.get("server_name")
    library_name = service_call.data["library_name"]

    plex_server = get_plex_server(hass, plex_server_name)

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

    if not plex_servers:
        raise HomeAssistantError("No Plex servers available")

    if plex_server_name:
        plex_server = next(
            (x for x in plex_servers if x.friendly_name == plex_server_name), None
        )
        if plex_server is not None:
            return plex_server
        friendly_names = [x.friendly_name for x in plex_servers]
        raise HomeAssistantError(
            f"Requested Plex server '{plex_server_name}' not found in {friendly_names}"
        )

    if len(plex_servers) == 1:
        return next(iter(plex_servers))

    friendly_names = [x.friendly_name for x in plex_servers]
    raise HomeAssistantError(
        f"Multiple Plex servers configured, choose with 'plex_server' key: {friendly_names}"
    )


def lookup_plex_media(hass, content_type, content_id):
    """Look up Plex media for other integrations using media_player.play_media service payloads."""
    content = json.loads(content_id)

    if isinstance(content, int):
        content = {"plex_key": content}
        content_type = DOMAIN

    plex_server_name = content.pop("plex_server", None)
    shuffle = content.pop("shuffle", 0)

    plex_server = get_plex_server(hass, plex_server_name=plex_server_name)

    media = plex_server.lookup_media(content_type, **content)
    if media is None:
        raise HomeAssistantError(f"Plex media not found using payload: '{content_id}'")

    playqueue = plex_server.create_playqueue(media, shuffle=shuffle)
    return (playqueue, plex_server)


def play_on_sonos(hass, content_type, content_id, speaker_name):
    """Play music on a connected Sonos speaker using Plex APIs.

    Called by Sonos 'media_player.play_media' service.
    """
    media, plex_server = lookup_plex_media(hass, content_type, content_id)
    sonos_speaker = plex_server.account.sonos_speaker(speaker_name)
    if sonos_speaker is None:
        message = f"Sonos speaker '{speaker_name}' is not associated with '{plex_server.friendly_name}'"
        _LOGGER.error(message)
        raise HomeAssistantError(message)
    sonos_speaker.playMedia(media)
