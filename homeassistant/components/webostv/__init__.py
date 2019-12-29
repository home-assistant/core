"""Support for WebOS TV."""
import asyncio
import logging

from aiopylgtv import PyLGTVCmdException, PyLGTVPairException, WebOsClient
import voluptuous as vol
from websockets.exceptions import ConnectionClosed

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CUSTOMIZE,
    CONF_FILENAME,
    CONF_HOST,
    CONF_ICON,
    CONF_NAME,
    ENTITY_MATCH_ALL,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

DOMAIN = "webostv"

CONF_SOURCES = "sources"
CONF_ON_ACTION = "turn_on_action"
CONF_STANDBY_CONNECTION = "standby_connection"
DEFAULT_NAME = "LG webOS Smart TV"
WEBOSTV_CONFIG_FILE = "webostv.conf"

SERVICE_BUTTON = "button"
ATTR_BUTTON = "button"

SERVICE_COMMAND = "command"
ATTR_COMMAND = "command"

CUSTOMIZE_SCHEMA = vol.Schema(
    {vol.Optional(CONF_SOURCES): vol.All(cv.ensure_list, [cv.string])}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional(CONF_CUSTOMIZE, default={}): CUSTOMIZE_SCHEMA,
                        vol.Optional(
                            CONF_FILENAME, default=WEBOSTV_CONFIG_FILE
                        ): cv.string,
                        vol.Optional(CONF_HOST): cv.string,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                        vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
                        vol.Optional(
                            CONF_STANDBY_CONNECTION, default=False
                        ): cv.boolean,
                        vol.Optional(CONF_ICON): cv.string,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)

CALL_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids})

BUTTON_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_BUTTON): cv.string})

COMMAND_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_COMMAND): cv.string})

SERVICE_TO_METHOD = {
    SERVICE_BUTTON: {"method": "async_button", "schema": BUTTON_SCHEMA},
    SERVICE_COMMAND: {"method": "async_commmand", "schema": COMMAND_SCHEMA},
}

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the LG WebOS TV platform."""
    hass.data[DOMAIN] = {}

    tasks = [async_setup_tv(hass, config, conf) for conf in config.get(DOMAIN, [])]
    if tasks:
        await asyncio.gather(*tasks)

    async def async_service_handler(service):
        method = SERVICE_TO_METHOD.get(service.service)
        params = {
            key: value for key, value in service.data.items() if key != "entity_id"
        }
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        target_players = []
        for entry in hass.data[DOMAIN].values():
            player = entry["media_player"]
            if entity_ids == ENTITY_MATCH_ALL or player.entity_id in entity_ids:
                target_players.append(player)

        calls = []
        for player in target_players:
            calls.append(getattr(player, method["method"])(**params))

        if calls:
            await asyncio.gather(*calls)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service]["schema"]
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=schema
        )

    return True


async def async_setup_tv(hass, config, conf):
    """Set up a LG WebOS TV based on host parameter."""

    host = conf.get(CONF_HOST)
    standby_connection = conf.get(CONF_STANDBY_CONNECTION)
    config_file = hass.config.path(conf.get(CONF_FILENAME))

    client = WebOsClient(host, config_file, standby_connection=standby_connection)

    hass.data[DOMAIN][host] = {"client": client}

    if client.is_registered():
        await async_setup_tv_finalize(hass, config, conf, client)
    else:
        _LOGGER.warning("LG webOS TV %s needs to be paired", host)
        await async_request_configuration(hass, config, conf, client)

    async def async_on_stop(event):
        """Unregister callbacks and disconnect."""
        for conf in hass.data[DOMAIN].values():
            client = conf["client"]
            client.clear_state_update_callbacks()
            hass.async_create_task(client.disconnect())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_on_stop)


async def async_connect(client):
    """Attempt a connection, but fail gracefully if tv is off for example."""
    try:
        await client.connect()
    except (
        OSError,
        ConnectionClosed,
        ConnectionRefusedError,
        asyncio.TimeoutError,
        asyncio.CancelledError,
        PyLGTVPairException,
        PyLGTVCmdException,
    ):
        pass


async def async_setup_tv_finalize(hass, config, conf, client):
    """Make initial connection attempt and call platform setup."""
    hass.async_create_task(async_connect(client))
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("media_player", DOMAIN, conf, config)
    )
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("notify", DOMAIN, conf, config)
    )


async def async_request_configuration(hass, config, conf, client):
    """Request configuration steps from the user."""
    host = conf.get(CONF_HOST)
    name = conf.get(CONF_NAME)
    configurator = hass.components.configurator

    _LOGGER.warning("request configuration")

    async def lgtv_configuration_callback(data):
        """Handle actions when configuration callback is called."""
        try:
            await client.connect()
        except PyLGTVPairException:
            _LOGGER.warning("Connected to LG webOS TV %s but not paired", host)
            return
        except (
            OSError,
            ConnectionClosed,
            ConnectionRefusedError,
            asyncio.TimeoutError,
            asyncio.CancelledError,
            PyLGTVCmdException,
        ):
            _LOGGER.error("Unable to connect to host %s", host)
            return

        await async_setup_tv_finalize(hass, config, conf, client)
        configurator.async_request_done(request_id)

    _LOGGER.warning("adding host to configuring")
    request_id = configurator.async_request_config(
        name,
        lgtv_configuration_callback,
        description="Click start and accept the pairing request on your TV.",
        description_image="/static/images/config_webos.png",
        submit_caption="Start pairing request",
    )
