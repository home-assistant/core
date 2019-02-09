"""
Support for controlling Sisyphus Kinetic Art Tables.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sisyphus/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

REQUIREMENTS = ['sisyphus-control==2.1']

_LOGGER = logging.getLogger(__name__)

DATA_SISYPHUS = 'sisyphus'
DOMAIN = 'sisyphus'

AUTODETECT_SCHEMA = vol.Schema({})

TABLE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
})

TABLES_SCHEMA = vol.Schema([TABLE_SCHEMA])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Any(AUTODETECT_SCHEMA, TABLES_SCHEMA),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the sisyphus component."""
    from sisyphus_control import Table
    tables = hass.data.setdefault(DATA_SISYPHUS, {})
    table_configs = config.get(DOMAIN)
    session = async_get_clientsession(hass)

    async def add_table(host, name=None):
        """Add platforms for a single table with the given hostname."""
        table = await Table.connect(host, session)
        if name is None:
            name = table.name
        tables[name] = table
        _LOGGER.debug("Connected to %s at %s", name, host)

        hass.async_create_task(async_load_platform(
            hass, 'light', DOMAIN, {
                CONF_NAME: name,
            }, config
        ))
        hass.async_create_task(async_load_platform(
            hass, 'media_player', DOMAIN, {
                CONF_NAME: name,
                CONF_HOST: host,
            }, config
        ))

    if isinstance(table_configs, dict):  # AUTODETECT_SCHEMA
        for ip_address in await Table.find_table_ips(session):
            await add_table(ip_address)
    else:  # TABLES_SCHEMA
        for conf in table_configs:
            await add_table(conf[CONF_HOST], conf[CONF_NAME])

    async def close_tables(*args):
        """Close all table objects."""
        tasks = [table.close() for table in tables.values()]
        if tasks:
            await asyncio.wait(tasks)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_tables)

    return True
