"""Support to embed Plex."""
import logging

import plexapi.exceptions
import voluptuous as vol

from homeassistant.components.discovery import SERVICE_PLEX
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.util.json import load_json, save_json

from .const import (
    CONF_USE_EPISODE_ART,
    CONF_SHOW_ALL_CONTROLS,
    CONF_REMOVE_UNAVAILABLE_CLIENTS,
    CONF_CLIENT_REMOVE_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN as PLEX_DOMAIN,
    PLATFORMS,
    PLEX_CONFIG_FILE,
    PLEX_MEDIA_PLAYER_OPTIONS,
    SERVERS,
)
from .server import PlexServer

MEDIA_PLAYER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_USE_EPISODE_ART, default=False): cv.boolean,
        vol.Optional(CONF_SHOW_ALL_CONTROLS, default=False): cv.boolean,
        vol.Optional(CONF_REMOVE_UNAVAILABLE_CLIENTS, default=True): cv.boolean,
        vol.Optional(CONF_CLIENT_REMOVE_INTERVAL, default=600): cv.positive_int,
    }
)

SERVER_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(MP_DOMAIN, default={}): MEDIA_PLAYER_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema({PLEX_DOMAIN: SERVER_CONFIG_SCHEMA}, extra=vol.ALLOW_EXTRA)

_CONFIGURING = {}
_LOGGER = logging.getLogger(__package__)


def setup(hass, config):
    """Set up the Plex component."""

    def server_discovered(service, info):
        """Pass back discovered Plex server details."""
        _LOGGER.info("Discovered Plex server: %s:%s", info["host"], info["port"])
        info["discovered_plex"] = True
        setup(hass, info)

    def connect_plex_server(plex_server):
        """Create shared PlexServer instance."""
        try:
            plex_server.connect()
        except (
            plexapi.exceptions.BadRequest,
            plexapi.exceptions.Unauthorized,
            plexapi.exceptions.NotFound,
        ) as error:
            _LOGGER.info(error)
            return False
        else:
            hass.data[PLEX_DOMAIN][SERVERS][
                plex_server.machine_identifier
            ] = plex_server

            host_and_port = plex_server.url_in_use.split("/")[-1]
            if host_and_port in _CONFIGURING:
                request_id = _CONFIGURING.pop(host_and_port)
                configurator = hass.components.configurator
                configurator.request_done(request_id)
                _LOGGER.debug("Discovery configuration done")

            return True

    hass.data.setdefault(PLEX_DOMAIN, {SERVERS: {}})

    if hass.data[PLEX_DOMAIN][SERVERS]:
        _LOGGER.debug("Plex server already configured")
        return

    # Prefer configuration
    plex_config = config.get(PLEX_DOMAIN, {})
    # Otherwise use plex.conf
    file_config = load_json(hass.config.path(PLEX_CONFIG_FILE))
    # Fallback to discovery/configurator
    discovered = config.pop("discovered_plex", False)
    if not plex_config and discovered:
        plex_config = config

    if plex_config:
        hass.data[PLEX_MEDIA_PLAYER_OPTIONS] = plex_config.get(MP_DOMAIN)
        host = plex_config[CONF_HOST]
        port = plex_config[CONF_PORT]
        token = plex_config.get(CONF_TOKEN)
        has_ssl = plex_config.get(CONF_SSL)
        verify_ssl = plex_config.get(CONF_VERIFY_SSL)
    elif file_config:
        host_and_port, host_config = file_config.popitem()
        host, port = host_and_port.split(":")
        token = host_config[CONF_TOKEN]
        has_ssl = host_config[CONF_SSL]
        verify_ssl = host_config["verify"]
    else:
        discovery.listen(hass, SERVICE_PLEX, server_discovered)
        return True

    http_prefix = "https" if has_ssl else "http"
    url = f"{http_prefix}://{host}:{port}"

    server_config = {CONF_URL: url, CONF_TOKEN: token, CONF_VERIFY_SSL: verify_ssl}

    if not hass.data.get(PLEX_MEDIA_PLAYER_OPTIONS):
        hass.data[PLEX_MEDIA_PLAYER_OPTIONS] = {
            CONF_USE_EPISODE_ART: False,
            CONF_SHOW_ALL_CONTROLS: False,
            CONF_REMOVE_UNAVAILABLE_CLIENTS: True,
            CONF_CLIENT_REMOVE_INTERVAL: 600,
        }

    plex_server = PlexServer(server_config)
    if connect_plex_server(plex_server):
        if discovered:
            # Write plex.conf if created via discovery/configurator
            save_json(
                hass.config.path(PLEX_CONFIG_FILE),
                {
                    f"{host}:{port}": {
                        "token": token,
                        "ssl": has_ssl,
                        "verify": verify_ssl,
                    }
                },
            )

        for platform in PLATFORMS:
            hass.helpers.discovery.load_platform(platform, PLEX_DOMAIN, {}, config)
    else:
        request_configuration(hass, f"{host}:{port}")

    return True


def request_configuration(hass, host_and_port):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    if host_and_port in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host_and_port], "Failed to register, please try again."
        )

        return

    def plex_configuration_callback(data):
        """Handle configuration changes."""
        host, port = host_and_port.split(":")
        callback_config = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_TOKEN: data.get("token"),
            CONF_SSL: cv.boolean(data.get("has_ssl")),
            CONF_VERIFY_SSL: cv.boolean(data.get("verify_ssl")),
            "discovered_plex": True,
        }
        setup(hass, callback_config)

    _CONFIGURING[host_and_port] = configurator.request_config(
        "Plex Media Server",
        plex_configuration_callback,
        description="Enter the X-Plex-Token",
        entity_picture="/static/images/logo_plex_mediaserver.png",
        submit_caption="Confirm",
        fields=[
            {"id": "token", "name": "X-Plex-Token", "type": ""},
            {"id": "has_ssl", "name": "Use SSL", "type": ""},
            {"id": "verify_ssl", "name": "Verify SSL", "type": ""},
        ],
    )
