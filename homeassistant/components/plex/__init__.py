"""Support to embed Plex."""
import asyncio
import functools
import json
import logging

import plexapi.exceptions
from plexwebsocket import PlexWebsocket
import requests.exceptions
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_URL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DISPATCHERS,
    DOMAIN as PLEX_DOMAIN,
    PLATFORMS,
    PLATFORMS_COMPLETED,
    PLEX_SERVER_CONFIG,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    SERVERS,
    SERVICE_PLAY_ON_SONOS,
    WEBSOCKETS,
)
from .errors import ShouldUpdateConfigEntry
from .server import PlexServer
from .services import async_setup_services

_LOGGER = logging.getLogger(__package__)


async def async_setup(hass, config):
    """Set up the Plex component."""
    hass.data.setdefault(
        PLEX_DOMAIN,
        {SERVERS: {}, DISPATCHERS: {}, WEBSOCKETS: {}, PLATFORMS_COMPLETED: {}},
    )

    await async_setup_services(hass)

    return True


async def async_setup_entry(hass, entry):
    """Set up Plex from a config entry."""
    server_config = entry.data[PLEX_SERVER_CONFIG]

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_SERVER_IDENTIFIER]
        )

    if MP_DOMAIN not in entry.options:
        options = dict(entry.options)
        options.setdefault(MP_DOMAIN, {})
        hass.config_entries.async_update_entry(entry, options=options)

    plex_server = PlexServer(
        hass, server_config, entry.data[CONF_SERVER_IDENTIFIER], entry.options
    )
    try:
        await hass.async_add_executor_job(plex_server.connect)
    except ShouldUpdateConfigEntry:
        new_server_data = {
            **entry.data[PLEX_SERVER_CONFIG],
            CONF_URL: plex_server.url_in_use,
            CONF_SERVER: plex_server.friendly_name,
        }
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, PLEX_SERVER_CONFIG: new_server_data}
        )
    except requests.exceptions.ConnectionError as error:
        _LOGGER.error(
            "Plex server (%s) could not be reached: [%s]",
            server_config[CONF_URL],
            error,
        )
        raise ConfigEntryNotReady from error
    except (
        plexapi.exceptions.BadRequest,
        plexapi.exceptions.Unauthorized,
        plexapi.exceptions.NotFound,
    ) as error:
        _LOGGER.error(
            "Login to %s failed, verify token and SSL settings: [%s]",
            entry.data[CONF_SERVER],
            error,
        )
        return False

    _LOGGER.debug(
        "Connected to: %s (%s)", plex_server.friendly_name, plex_server.url_in_use
    )
    server_id = plex_server.machine_identifier
    hass.data[PLEX_DOMAIN][SERVERS][server_id] = plex_server
    hass.data[PLEX_DOMAIN][PLATFORMS_COMPLETED][server_id] = set()

    entry.add_update_listener(async_options_updated)

    unsub = async_dispatcher_connect(
        hass,
        PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id),
        plex_server.async_update_platforms,
    )
    hass.data[PLEX_DOMAIN][DISPATCHERS].setdefault(server_id, [])
    hass.data[PLEX_DOMAIN][DISPATCHERS][server_id].append(unsub)

    def update_plex():
        async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))

    session = async_get_clientsession(hass)
    verify_ssl = server_config.get(CONF_VERIFY_SSL)
    websocket = PlexWebsocket(
        plex_server.plex_server, update_plex, session=session, verify_ssl=verify_ssl
    )
    hass.data[PLEX_DOMAIN][WEBSOCKETS][server_id] = websocket

    def start_websocket_session(platform, _):
        hass.data[PLEX_DOMAIN][PLATFORMS_COMPLETED][server_id].add(platform)
        if hass.data[PLEX_DOMAIN][PLATFORMS_COMPLETED][server_id] == PLATFORMS:
            hass.loop.create_task(websocket.listen())

    def close_websocket_session(_):
        websocket.close()

    unsub = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, close_websocket_session
    )
    hass.data[PLEX_DOMAIN][DISPATCHERS][server_id].append(unsub)

    for platform in PLATFORMS:
        task = hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
        task.add_done_callback(functools.partial(start_websocket_session, platform))

    async def async_play_on_sonos_service(service_call):
        await hass.async_add_executor_job(play_on_sonos, hass, service_call)

    play_on_sonos_schema = vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Required(ATTR_MEDIA_CONTENT_ID): str,
            vol.Optional(ATTR_MEDIA_CONTENT_TYPE): vol.In("music"),
        }
    )

    def get_plex_account(plex_server):
        try:
            return plex_server.account
        except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized):
            return None

    plex_account = await hass.async_add_executor_job(get_plex_account, plex_server)
    if plex_account:
        hass.services.async_register(
            PLEX_DOMAIN,
            SERVICE_PLAY_ON_SONOS,
            async_play_on_sonos_service,
            schema=play_on_sonos_schema,
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    server_id = entry.data[CONF_SERVER_IDENTIFIER]

    websocket = hass.data[PLEX_DOMAIN][WEBSOCKETS].pop(server_id)
    websocket.close()

    dispatchers = hass.data[PLEX_DOMAIN][DISPATCHERS].pop(server_id)
    for unsub in dispatchers:
        unsub()

    tasks = [
        hass.config_entries.async_forward_entry_unload(entry, platform)
        for platform in PLATFORMS
    ]
    await asyncio.gather(*tasks)

    hass.data[PLEX_DOMAIN][SERVERS].pop(server_id)

    return True


async def async_options_updated(hass, entry):
    """Triggered by config entry options updates."""
    server_id = entry.data[CONF_SERVER_IDENTIFIER]
    hass.data[PLEX_DOMAIN][SERVERS][server_id].options = entry.options


def play_on_sonos(hass, service_call):
    """Play Plex media on a linked Sonos device."""
    entity_id = service_call.data[ATTR_ENTITY_ID]
    content_id = service_call.data[ATTR_MEDIA_CONTENT_ID]
    content = json.loads(content_id)

    sonos = hass.components.sonos
    try:
        sonos_name = sonos.get_coordinator_name(entity_id)
    except HomeAssistantError as err:
        _LOGGER.error("Cannot get Sonos device: %s", err)
        return

    if isinstance(content, int):
        content = {"plex_key": content}
        content_type = PLEX_DOMAIN
    else:
        content_type = "music"

    plex_server_name = content.get("plex_server")
    shuffle = content.pop("shuffle", 0)

    plex_servers = hass.data[PLEX_DOMAIN][SERVERS].values()
    if plex_server_name:
        plex_server = [x for x in plex_servers if x.friendly_name == plex_server_name]
        if not plex_server:
            _LOGGER.error(
                "Requested Plex server '%s' not found in %s",
                plex_server_name,
                list(map(lambda x: x.friendly_name, plex_servers)),
            )
            return
    else:
        plex_server = next(iter(plex_servers))

    sonos_speaker = plex_server.account.sonos_speaker(sonos_name)
    if sonos_speaker is None:
        _LOGGER.error(
            "Sonos speaker '%s' could not be found on this Plex account", sonos_name
        )
        return

    media = plex_server.lookup_media(content_type, **content)
    if media is None:
        _LOGGER.error("Media could not be found: %s", content)
        return

    _LOGGER.debug("Attempting to play '%s' on %s", media, sonos_speaker)
    playqueue = plex_server.create_playqueue(media, shuffle=shuffle)
    sonos_speaker.playMedia(playqueue)
