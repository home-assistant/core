"""Support to embed Plex."""
from functools import partial
import logging

import plexapi.exceptions
from plexapi.gdm import GDM
from plexwebsocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STOPPED,
    PlexWebsocket,
)
import requests.exceptions

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN, BrowseError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.network import is_internal_request
from homeassistant.helpers.typing import ConfigType

from .const import (
    CLIENT_SCAN_INTERVAL,
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DISPATCHERS,
    DOMAIN,
    INVALID_TOKEN_MESSAGE,
    PLATFORMS,
    PLATFORMS_COMPLETED,
    PLEX_SERVER_CONFIG,
    PLEX_UPDATE_LIBRARY_SIGNAL,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    PLEX_URI_SCHEME,
    SERVERS,
    WEBSOCKETS,
)
from .errors import ShouldUpdateConfigEntry
from .helpers import PlexData, get_plex_data
from .media_browser import browse_media
from .server import PlexServer
from .services import async_setup_services
from .view import PlexImageView

_LOGGER = logging.getLogger(__package__)


def is_plex_media_id(media_content_id):
    """Return whether the media_content_id is a valid Plex media_id."""
    return media_content_id and media_content_id.startswith(PLEX_URI_SCHEME)


async def async_browse_media(hass, media_content_type, media_content_id, platform=None):
    """Browse Plex media."""
    plex_server = next(iter(get_plex_data(hass)[SERVERS].values()), None)
    if not plex_server:
        raise BrowseError("No Plex servers available")
    is_internal = is_internal_request(hass)
    return await hass.async_add_executor_job(
        partial(
            browse_media,
            hass,
            is_internal,
            media_content_type,
            media_content_id,
            platform=platform,
        )
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Plex component."""
    gdm = GDM()

    def gdm_scan():
        _LOGGER.debug("Scanning for GDM clients")
        gdm.scan(scan_for_clients=True)

    debouncer = Debouncer[None](
        hass,
        _LOGGER,
        cooldown=10,
        immediate=True,
        function=gdm_scan,
    ).async_call

    hass_data = PlexData(
        servers={},
        dispatchers={},
        websockets={},
        platforms_completed={},
        gdm_scanner=gdm,
        gdm_debouncer=debouncer,
    )
    hass.data.setdefault(DOMAIN, hass_data)

    await async_setup_services(hass)

    hass.http.register_view(PlexImageView())

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
        hass,
        server_config,
        entry.data[CONF_SERVER_IDENTIFIER],
        entry.options,
        entry.entry_id,
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
        raise ConfigEntryNotReady from error
    except plexapi.exceptions.Unauthorized as ex:
        raise ConfigEntryAuthFailed(
            "Token not accepted, please reauthenticate Plex server"
            f" '{entry.data[CONF_SERVER]}'"
        ) from ex
    except (
        plexapi.exceptions.BadRequest,
        plexapi.exceptions.NotFound,
    ) as error:
        if INVALID_TOKEN_MESSAGE in str(error):
            raise ConfigEntryAuthFailed(
                "Token not accepted, please reauthenticate Plex server"
                f" '{entry.data[CONF_SERVER]}'"
            ) from error
        _LOGGER.error(
            "Login to %s failed, verify token and SSL settings: [%s]",
            entry.data[CONF_SERVER],
            error,
        )
        # Retry as setups behind a proxy can return transient 404 or 502 errors
        raise ConfigEntryNotReady from error

    _LOGGER.debug(
        "Connected to: %s (%s)", plex_server.friendly_name, plex_server.url_in_use
    )
    server_id = plex_server.machine_identifier
    hass_data = get_plex_data(hass)
    hass_data[SERVERS][server_id] = plex_server
    hass_data[PLATFORMS_COMPLETED][server_id] = set()

    entry.add_update_listener(async_options_updated)

    unsub = async_dispatcher_connect(
        hass,
        PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id),
        plex_server.async_update_platforms,
    )
    hass_data[DISPATCHERS].setdefault(server_id, [])
    hass_data[DISPATCHERS][server_id].append(unsub)

    @callback
    def plex_websocket_callback(msgtype, data, error):
        """Handle callbacks from plexwebsocket library."""
        if msgtype == SIGNAL_CONNECTION_STATE:
            if data == STATE_CONNECTED:
                _LOGGER.debug("Websocket to %s successful", entry.data[CONF_SERVER])
                hass.async_create_task(plex_server.async_update_platforms())
            elif data == STATE_DISCONNECTED:
                _LOGGER.debug(
                    "Websocket to %s disconnected, retrying", entry.data[CONF_SERVER]
                )
            # Stopped websockets without errors are expected during shutdown and ignored
            elif data == STATE_STOPPED and error:
                _LOGGER.error(
                    "Websocket to %s failed, aborting [Error: %s]",
                    entry.data[CONF_SERVER],
                    error,
                )
                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

        elif msgtype == "playing":
            hass.async_create_task(plex_server.async_update_session(data))
        elif msgtype == "status":
            if data["StatusNotification"][0]["title"] == "Library scan complete":
                async_dispatcher_send(
                    hass,
                    PLEX_UPDATE_LIBRARY_SIGNAL.format(server_id),
                )

    session = async_get_clientsession(hass)
    subscriptions = ["playing", "status"]
    verify_ssl = server_config.get(CONF_VERIFY_SSL)
    websocket = PlexWebsocket(
        plex_server.plex_server,
        plex_websocket_callback,
        subscriptions=subscriptions,
        session=session,
        verify_ssl=verify_ssl,
    )
    hass_data[WEBSOCKETS][server_id] = websocket

    def start_websocket_session(platform):
        hass_data[PLATFORMS_COMPLETED][server_id].add(platform)
        if hass_data[PLATFORMS_COMPLETED][server_id] == PLATFORMS:
            hass.loop.create_task(websocket.listen())

    def close_websocket_session(_):
        websocket.close()

    unsub = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, close_websocket_session
    )
    hass_data[DISPATCHERS][server_id].append(unsub)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    for platform in PLATFORMS:
        start_websocket_session(platform)

    async_cleanup_plex_devices(hass, entry)

    def get_plex_account(plex_server):
        try:
            return plex_server.account
        except (plexapi.exceptions.BadRequest, plexapi.exceptions.Unauthorized):
            return None

    await hass.async_add_executor_job(get_plex_account, plex_server)

    @callback
    def scheduled_client_scan(_):
        _LOGGER.debug("Scheduled scan for new clients on %s", plex_server.friendly_name)
        async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            scheduled_client_scan,
            CLIENT_SCAN_INTERVAL,
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    server_id = entry.data[CONF_SERVER_IDENTIFIER]

    hass_data = get_plex_data(hass)
    websocket = hass_data[WEBSOCKETS].pop(server_id)
    websocket.close()

    dispatchers = hass_data[DISPATCHERS].pop(server_id)
    for unsub in dispatchers:
        unsub()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass_data[SERVERS].pop(server_id)

    return unload_ok


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Triggered by config entry options updates."""
    server_id = entry.data[CONF_SERVER_IDENTIFIER]

    hass_data = get_plex_data(hass)
    # Guard incomplete setup during reauth flows
    if server_id in hass_data[SERVERS]:
        hass_data[SERVERS][server_id].options = entry.options


@callback
def async_cleanup_plex_devices(hass, entry):
    """Clean up old and invalid devices from the registry."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    for device_entry in device_entries:
        if (
            len(
                er.async_entries_for_device(
                    entity_registry, device_entry.id, include_disabled_entities=True
                )
            )
            == 0
        ):
            _LOGGER.debug(
                "Removing orphaned device: %s / %s",
                device_entry.name,
                device_entry.identifiers,
            )
            device_registry.async_remove_device(device_entry.id)
