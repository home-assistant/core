"""
Enables control of Sisyphus Kinetic Art Tables.

Each table is exposed as a light and a media player.
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP
)
from homeassistant.helpers.discovery import async_load_platform

REQUIREMENTS = ['sisyphus-control==2.0.0']

_LOGGER = logging.getLogger(__name__)

DATA_SISYPHUS = 'sisyphus'
DOMAIN = 'sisyphus'

AUTODETECT_SCHEMA = vol.Schema({
    DOMAIN: {},
}, extra=vol.ALLOW_EXTRA)

TABLES_SCHEMA = vol.Schema({
    DOMAIN: [
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_HOST): cv.string,
        },
    ],
}, extra=vol.ALLOW_EXTRA)

CONFIG_SCHEMA = vol.Any(AUTODETECT_SCHEMA, TABLES_SCHEMA)


async def async_setup(hass, config):
    """Set up the sisyphus component."""
    from sisyphus_control import Table
    tables = hass.data.setdefault(DATA_SISYPHUS, {})
    table_configs = config.get(DOMAIN)

    async def add_table(host, name=None):
        """Add platforms for a single table with the given hostname."""
        table = await Table.connect(host)
        if name is None:
            name = table.name
        tables[name] = table
        _LOGGER.debug("Connected to %s at %s", name, host)

        hass.async_add_job(async_load_platform(
            hass, 'light', 'sisyphus', {
                CONF_NAME: name,
            }, config
        ))
        hass.async_add_job(async_load_platform(
            hass, 'media_player', 'sisyphus', {
                CONF_NAME: name,
                CONF_HOST: host,
            }, config
        ))

    if isinstance(table_configs, dict):  # AUTODETECT_SCHEMA
        for ip_address in await Table.find_table_ips():
            await add_table(ip_address)
    else:  # TABLES_SCHEMA
        for conf in table_configs:
            if conf.get(CONF_HOST) is not None:
                await add_table(conf.get(CONF_HOST), conf.get(CONF_NAME))

    async def close_tables(*args):
        """Close all table objects."""
        for table in tables.values():
            await table.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_tables)

    return True
