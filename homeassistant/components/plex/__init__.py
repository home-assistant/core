"""Support to embed Plex."""
import logging

import plexapi.exceptions
import requests.exceptions
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
    CONF_SERVER,
    CONF_USE_EPISODE_ART,
    CONF_SHOW_ALL_CONTROLS,
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
    }
)

SERVER_CONFIG_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(CONF_HOST): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_TOKEN): cv.string,
            vol.Optional(CONF_SERVER): cv.string,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
            vol.Optional(MP_DOMAIN, default={}): MEDIA_PLAYER_SCHEMA,
        },
        cv.has_at_least_one_key(CONF_HOST, CONF_TOKEN),
    )
)

CONFIG_SCHEMA = vol.Schema({PLEX_DOMAIN: SERVER_CONFIG_SCHEMA}, extra=vol.ALLOW_EXTRA)

CONFIGURING = "configuring"
_LOGGER = logging.getLogger(__package__)


def setup(hass, config):
    """Set up the Plex component."""

    def server_discovered(service, info):
        """Pass back discovered Plex server details."""
        if hass.data[PLEX_DOMAIN][SERVERS]:
            _LOGGER.debug("Plex server already configured, ignoring discovery.")
            return
        _LOGGER.debug("Discovered Plex server: %s:%s", info["host"], info["port"])
        setup_plex(discovery_info=info)

    def setup_plex(config=None, discovery_info=None, configurator_info=None):
        """Return assembled server_config dict."""
        json_file = hass.config.path(PLEX_CONFIG_FILE)
        file_config = load_json(json_file)
        host_and_port = None

        if config:
            server_config = config
            if CONF_HOST in server_config:
                host_and_port = (
                    f"{server_config.pop(CONF_HOST)}:{server_config.pop(CONF_PORT)}"
                )
            if MP_DOMAIN in server_config:
                hass.data[PLEX_MEDIA_PLAYER_OPTIONS] = server_config.pop(MP_DOMAIN)
        elif file_config:
            _LOGGER.debug("Loading config from %s", json_file)
            host_and_port, server_config = file_config.popitem()
            server_config[CONF_VERIFY_SSL] = server_config.pop("verify")
        elif discovery_info:
            server_config = {}
            host_and_port = f"{discovery_info[CONF_HOST]}:{discovery_info[CONF_PORT]}"
        elif configurator_info:
            server_config = configurator_info
            host_and_port = server_config["host_and_port"]
        else:
            discovery.listen(hass, SERVICE_PLEX, server_discovered)
            return True

        if host_and_port:
            use_ssl = server_config.get(CONF_SSL, DEFAULT_SSL)
            http_prefix = "https" if use_ssl else "http"
            server_config[CONF_URL] = f"{http_prefix}://{host_and_port}"

        plex_server = PlexServer(server_config)
        try:
            plex_server.connect()
        except requests.exceptions.ConnectionError as error:
            _LOGGER.error(
                "Plex server could not be reached, please verify host and port: [%s]",
                error,
            )
            return False
        except (
            plexapi.exceptions.BadRequest,
            plexapi.exceptions.Unauthorized,
            plexapi.exceptions.NotFound,
        ) as error:
            _LOGGER.error(
                "Connection to Plex server failed, please verify token and SSL settings: [%s]",
                error,
            )
            request_configuration(host_and_port)
            return False
        else:
            hass.data[PLEX_DOMAIN][SERVERS][
                plex_server.machine_identifier
            ] = plex_server

            if host_and_port in hass.data[PLEX_DOMAIN][CONFIGURING]:
                request_id = hass.data[PLEX_DOMAIN][CONFIGURING].pop(host_and_port)
                configurator = hass.components.configurator
                configurator.request_done(request_id)
                _LOGGER.debug("Discovery configuration done")
            if configurator_info:
                # Write plex.conf if created via discovery/configurator
                save_json(
                    hass.config.path(PLEX_CONFIG_FILE),
                    {
                        host_and_port: {
                            CONF_TOKEN: server_config[CONF_TOKEN],
                            CONF_SSL: use_ssl,
                            "verify": server_config[CONF_VERIFY_SSL],
                        }
                    },
                )

            if not hass.data.get(PLEX_MEDIA_PLAYER_OPTIONS):
                hass.data[PLEX_MEDIA_PLAYER_OPTIONS] = MEDIA_PLAYER_SCHEMA({})

            for platform in PLATFORMS:
                hass.helpers.discovery.load_platform(
                    platform, PLEX_DOMAIN, {}, original_config
                )

            return True

    def request_configuration(host_and_port):
        """Request configuration steps from the user."""
        configurator = hass.components.configurator
        if host_and_port in hass.data[PLEX_DOMAIN][CONFIGURING]:
            configurator.notify_errors(
                hass.data[PLEX_DOMAIN][CONFIGURING][host_and_port],
                "Failed to register, please try again.",
            )
            return

        def plex_configuration_callback(data):
            """Handle configuration changes."""
            config = {
                "host_and_port": host_and_port,
                CONF_TOKEN: data.get("token"),
                CONF_SSL: cv.boolean(data.get("ssl")),
                CONF_VERIFY_SSL: cv.boolean(data.get("verify_ssl")),
            }
            setup_plex(configurator_info=config)

        hass.data[PLEX_DOMAIN][CONFIGURING][
            host_and_port
        ] = configurator.request_config(
            "Plex Media Server",
            plex_configuration_callback,
            description="Enter the X-Plex-Token",
            entity_picture="/static/images/logo_plex_mediaserver.png",
            submit_caption="Confirm",
            fields=[
                {"id": "token", "name": "X-Plex-Token", "type": ""},
                {"id": "ssl", "name": "Use SSL", "type": ""},
                {"id": "verify_ssl", "name": "Verify SSL", "type": ""},
            ],
        )

    # End of inner functions.

    original_config = config

    hass.data.setdefault(PLEX_DOMAIN, {SERVERS: {}, CONFIGURING: {}})

    if hass.data[PLEX_DOMAIN][SERVERS]:
        _LOGGER.debug("Plex server already configured")
        return False

    plex_config = config.get(PLEX_DOMAIN, {})
    return setup_plex(config=plex_config)
