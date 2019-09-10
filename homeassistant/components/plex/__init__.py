"""Support to embed Plex."""
import logging

import plexapi.exceptions
import requests.exceptions
import voluptuous as vol

from homeassistant import config_entries
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
from homeassistant.util.json import load_json

from .const import (
    CONF_USE_EPISODE_ART,
    CONF_SHOW_ALL_CONTROLS,
    CONF_SERVER,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN as PLEX_DOMAIN,
    PLATFORMS,
    PLEX_CONFIG_FILE,
    PLEX_MEDIA_PLAYER_OPTIONS,
    PLEX_SERVER_CONFIG,
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

_LOGGER = logging.getLogger(__package__)


def setup(hass, config):
    """Set up the Plex component."""

    def server_discovered(service, info):
        """Pass discovered Plex server details to a config flow."""
        if hass.config_entries.async_entries(PLEX_DOMAIN):
            _LOGGER.debug("Plex server already configured, ignoring discovery.")
            return
        _LOGGER.debug("Discovered Plex server: %s:%s", info["host"], info["port"])
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                PLEX_DOMAIN,
                context={"source": config_entries.SOURCE_DISCOVERY},
                data=info,
            )
        )

    def setup_plex(config):
        """Pass configuration to a config flow."""
        json_file = hass.config.path(PLEX_CONFIG_FILE)
        file_config = load_json(json_file)

        if config:
            if MP_DOMAIN in config:
                hass.data[PLEX_MEDIA_PLAYER_OPTIONS] = config.pop(MP_DOMAIN)
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    PLEX_DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=config,
                )
            )
        elif file_config:
            if not hass.config_entries.async_entries(PLEX_DOMAIN):
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        PLEX_DOMAIN,
                        context={"source": "import_plex_conf"},
                        data=file_config,
                    )
                )
            else:
                _LOGGER.info("Legacy config file can be removed: %s", json_file)
        else:
            discovery.listen(hass, SERVICE_PLEX, server_discovered)

    hass.data.setdefault(PLEX_DOMAIN, {SERVERS: {}})

    plex_config = config.get(PLEX_DOMAIN, {})
    setup_plex(config=plex_config)

    return True


async def async_setup_entry(hass, entry):
    """Set up Plex from a config entry."""
    server_config = entry.data[PLEX_SERVER_CONFIG]

    plex_server = PlexServer(server_config)
    try:
        await hass.async_add_executor_job(plex_server.connect)
    except requests.exceptions.ConnectionError as error:
        _LOGGER.error(
            "Plex server (%s) could not be reached: [%s]",
            server_config[CONF_URL],
            error,
        )
        return False
    except (
        plexapi.exceptions.BadRequest,
        plexapi.exceptions.Unauthorized,
        plexapi.exceptions.NotFound,
    ) as error:
        _LOGGER.error(
            "Login to %s failed, verify token and SSL settings: [%s]",
            server_config[CONF_SERVER],
            error,
        )
        return False

    _LOGGER.debug(
        "Connected to: %s (%s)", plex_server.friendly_name, plex_server.url_in_use
    )
    hass.data[PLEX_DOMAIN][SERVERS][plex_server.machine_identifier] = plex_server

    if not hass.data.get(PLEX_MEDIA_PLAYER_OPTIONS):
        hass.data[PLEX_MEDIA_PLAYER_OPTIONS] = MEDIA_PLAYER_SCHEMA({})

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True
