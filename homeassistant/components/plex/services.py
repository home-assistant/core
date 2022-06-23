"""Services for the Plex integration."""
import json
import logging

from plexapi.exceptions import NotFound
import voluptuous as vol
from yarl import URL

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    PLEX_URI_SCHEME,
    SERVERS,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SCAN_CLIENTS,
)
from .errors import MediaNotFound
from .models import PlexMediaSearchResult

REFRESH_LIBRARY_SCHEMA = vol.Schema(
    {vol.Optional("server_name"): str, vol.Required("library_name"): str}
)

_LOGGER = logging.getLogger(__package__)


async def async_setup_services(hass):
    """Set up services for the Plex component."""

    async def async_refresh_library_service(service_call: ServiceCall) -> None:
        await hass.async_add_executor_job(refresh_library, hass, service_call)

    async def async_scan_clients_service(_: ServiceCall) -> None:
        _LOGGER.warning(
            "This service is deprecated in favor of the scan_clients button entity. "
            "Service calls will still work for now but the service will be removed in a future release"
        )
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


def refresh_library(hass: HomeAssistant, service_call: ServiceCall) -> None:
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


def get_plex_server(hass, plex_server_name=None, plex_server_id=None):
    """Retrieve a configured Plex server by name."""
    if DOMAIN not in hass.data:
        raise HomeAssistantError("Plex integration not configured")
    plex_servers = hass.data[DOMAIN][SERVERS].values()
    if not plex_servers:
        raise HomeAssistantError("No Plex servers available")

    if plex_server_id:
        return hass.data[DOMAIN][SERVERS][plex_server_id]

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


def process_plex_payload(
    hass, content_type, content_id, default_plex_server=None, supports_playqueues=True
) -> PlexMediaSearchResult:
    """Look up Plex media using media_player.play_media service payloads."""
    plex_server = default_plex_server
    extra_params = {}

    if content_id.startswith(PLEX_URI_SCHEME + "{"):
        # Handle the special payload of 'plex://{<json>}'
        content_id = content_id[len(PLEX_URI_SCHEME) :]
        content = json.loads(content_id)
    elif content_id.startswith(PLEX_URI_SCHEME):
        # Handle standard media_browser payloads
        plex_url = URL(content_id)
        if plex_url.name:
            if len(plex_url.parts) == 2:
                if plex_url.name == "search":
                    content = {}
                else:
                    content = int(plex_url.name)
            else:
                # For "special" items like radio stations
                content = plex_url.path
            server_id = plex_url.host
            plex_server = get_plex_server(hass, plex_server_id=server_id)
        else:
            # Handle legacy payloads without server_id in URL host position
            if plex_url.host == "search":
                content = {}
            else:
                content = int(plex_url.host)  # type: ignore[arg-type]
        extra_params = dict(plex_url.query)
    else:
        content = json.loads(content_id)

    if isinstance(content, dict):
        if plex_server_name := content.pop("plex_server", None):
            plex_server = get_plex_server(hass, plex_server_name)

    if not plex_server:
        plex_server = get_plex_server(hass)

    if content_type == "station":
        if not supports_playqueues:
            raise HomeAssistantError("Plex stations are not supported on this device")
        playqueue = plex_server.create_station_playqueue(content)
        return PlexMediaSearchResult(playqueue)

    if isinstance(content, int):
        content = {"plex_key": content}
        content_type = DOMAIN

    content.update(extra_params)

    if playqueue_id := content.pop("playqueue_id", None):
        if not supports_playqueues:
            raise HomeAssistantError("Plex playqueues are not supported on this device")
        try:
            playqueue = plex_server.get_playqueue(playqueue_id)
        except NotFound as err:
            raise MediaNotFound(
                f"PlayQueue '{playqueue_id}' could not be found"
            ) from err
        return PlexMediaSearchResult(playqueue, content)

    search_query = content.copy()
    shuffle = search_query.pop("shuffle", 0)

    # Remove internal kwargs before passing copy to plexapi
    for internal_key in ("resume", "offset"):
        search_query.pop(internal_key, None)

    media = plex_server.lookup_media(content_type, **search_query)

    if supports_playqueues and (isinstance(media, list) or shuffle):
        playqueue = plex_server.create_playqueue(
            media, includeRelated=0, shuffle=shuffle
        )
        return PlexMediaSearchResult(playqueue, content)

    return PlexMediaSearchResult(media, content)
