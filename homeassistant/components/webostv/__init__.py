"""Support for LG webOS Smart TV."""
from __future__ import annotations

from contextlib import suppress
import logging

from aiopylgtv import PyLGTVPairException, WebOsClient
import voluptuous as vol

from homeassistant.components import notify as hass_notify
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    CONF_CLIENT_SECRET,
    CONF_CUSTOMIZE,
    CONF_HOST,
    CONF_ICON,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_BUTTON,
    ATTR_CONFIG_ENTRY_ID,
    ATTR_PAYLOAD,
    ATTR_SOUND_OUTPUT,
    CONF_ON_ACTION,
    CONF_SOURCES,
    DATA_CONFIG_ENTRY,
    DATA_HASS_CONFIG,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
    SERVICE_BUTTON,
    SERVICE_COMMAND,
    SERVICE_SELECT_SOUND_OUTPUT,
    WEBOSTV_EXCEPTIONS,
)

CUSTOMIZE_SCHEMA = vol.Schema(
    {vol.Optional(CONF_SOURCES, default=[]): vol.All(cv.ensure_list, [cv.string])}
)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.All(
                cv.ensure_list,
                [
                    vol.Schema(
                        {
                            vol.Optional(CONF_CUSTOMIZE, default={}): CUSTOMIZE_SCHEMA,
                            vol.Required(CONF_HOST): cv.string,
                            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                            vol.Optional(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
                            vol.Optional(CONF_ICON): cv.string,
                        }
                    )
                ],
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

CALL_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids})

BUTTON_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_BUTTON): cv.string})

COMMAND_SCHEMA = CALL_SCHEMA.extend(
    {vol.Required(ATTR_COMMAND): cv.string, vol.Optional(ATTR_PAYLOAD): dict}
)

SOUND_OUTPUT_SCHEMA = CALL_SCHEMA.extend({vol.Required(ATTR_SOUND_OUTPUT): cv.string})

SERVICE_TO_METHOD = {
    SERVICE_BUTTON: {"method": "async_button", "schema": BUTTON_SCHEMA},
    SERVICE_COMMAND: {"method": "async_command", "schema": COMMAND_SCHEMA},
    SERVICE_SELECT_SOUND_OUTPUT: {
        "method": "async_select_sound_output",
        "schema": SOUND_OUTPUT_SCHEMA,
    },
}

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the LG WebOS TV platform."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_CONFIG_ENTRY, {})
    hass.data[DOMAIN][DATA_HASS_CONFIG] = config

    if DOMAIN not in config:
        return True

    for conf in config[DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
            )
        )

    return True


def _async_migrate_options_from_data(hass, config_entry):
    """Migrate options from data."""
    if config_entry.options:
        return

    config = config_entry.data
    options = {}

    # Get Preferred Sources
    if sources := config.get(CONF_CUSTOMIZE, {}).get(CONF_SOURCES):
        options[CONF_SOURCES] = sources
        if not isinstance(sources, list):
            options[CONF_SOURCES] = sources.split(",")

    hass.config_entries.async_update_entry(config_entry, options=options)


async def async_setup_entry(hass, config_entry):
    """Set the config entry up."""
    _async_migrate_options_from_data(hass, config_entry)

    host = config_entry.data[CONF_HOST]
    key = config_entry.data[CONF_CLIENT_SECRET]

    client = await WebOsClient.create(host, client_key=key)
    await async_connect(client)

    async def async_service_handler(service):
        method = SERVICE_TO_METHOD.get(service.service)
        data = service.data.copy()
        data["method"] = method["method"]
        async_dispatcher_send(hass, DOMAIN, data)

    for service, method in SERVICE_TO_METHOD.items():
        schema = method["schema"]
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=schema
        )

    hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id] = client
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            "notify",
            DOMAIN,
            {
                CONF_NAME: config_entry.title,
                ATTR_CONFIG_ENTRY_ID: config_entry.entry_id,
            },
            hass.data[DOMAIN][DATA_HASS_CONFIG],
        )
    )

    if not config_entry.update_listeners:
        config_entry.async_on_unload(
            config_entry.add_update_listener(async_update_options)
        )

    async def async_on_stop(_event):
        """Unregister callbacks and disconnect."""
        client.clear_state_update_callbacks()
        await client.disconnect()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_on_stop)
    )
    return True


async def async_update_options(hass, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_connect(client):
    """Attempt a connection, but fail gracefully if tv is off for example."""
    with suppress(WEBOSTV_EXCEPTIONS, PyLGTVPairException):
        await client.connect()


async def async_control_connect(host: str, key: str | None) -> WebOsClient:
    """LG Connection."""
    client = await WebOsClient.create(host, client_key=key)
    try:
        await client.connect()
    except PyLGTVPairException as err:
        _LOGGER.warning("Connected to LG webOS TV %s but not paired", host)
        raise PyLGTVPairException(err) from err

    return client


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    client = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)
        await hass_notify.async_reload(hass, DOMAIN)
        client.clear_state_update_callbacks()
        await client.disconnect()

    # unregister service calls, check if this is the last entry to unload
    if unload_ok and not hass.data[DOMAIN][DATA_CONFIG_ENTRY]:
        for service in SERVICE_TO_METHOD:
            hass.services.async_remove(DOMAIN, service)

    return unload_ok
