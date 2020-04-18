"""Support for controlling Sisyphus Kinetic Art Tables."""
import asyncio
import logging

from sisyphus_control import Table
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DATA_SISYPHUS = "sisyphus"
DOMAIN = "sisyphus"

AUTODETECT_SCHEMA = vol.Schema({})

TABLE_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Required(CONF_HOST): cv.string}
)

TABLES_SCHEMA = vol.Schema([TABLE_SCHEMA])

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Any(AUTODETECT_SCHEMA, TABLES_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Set up the sisyphus component."""

    class SocketIONoiseFilter(logging.Filter):
        """Filters out excessively verbose logs from SocketIO."""

        def filter(self, record):
            if "waiting for connection" in record.msg:
                return False
            return True

    logging.getLogger("socketIO-client").addFilter(SocketIONoiseFilter())
    tables = hass.data.setdefault(DATA_SISYPHUS, {})
    table_configs = config.get(DOMAIN)
    session = async_get_clientsession(hass)

    async def add_table(host, name=None):
        """Add platforms for a single table with the given hostname."""
        tables[host] = TableHolder(hass, session, host, name)

        hass.async_create_task(
            async_load_platform(hass, "light", DOMAIN, {CONF_HOST: host}, config)
        )
        hass.async_create_task(
            async_load_platform(hass, "media_player", DOMAIN, {CONF_HOST: host}, config)
        )

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


class TableHolder:
    """Holds table objects and makes them available to platforms."""

    def __init__(self, hass, session, host, name):
        """Initialize the table holder."""
        self._hass = hass
        self._session = session
        self._host = host
        self._name = name
        self._table = None
        self._table_task = None

    @property
    def available(self):
        """Return true if the table is responding to heartbeats."""
        if self._table_task and self._table_task.done():
            return self._table_task.result().is_connected
        return False

    @property
    def name(self):
        """Return the name of the table."""
        return self._name

    async def get_table(self):
        """Return the Table held by this holder, connecting to it if needed."""
        if self._table:
            return self._table

        if not self._table_task:
            self._table_task = self._hass.async_create_task(self._connect_table())

        return await self._table_task

    async def _connect_table(self):
        try:
            self._table = await Table.connect(self._host, self._session)
            if self._name is None:
                self._name = self._table.name
                _LOGGER.debug("Connected to %s at %s", self._name, self._host)
            return self._table
        finally:
            self._table_task = None

    async def close(self):
        """Close the table held by this holder, if any."""
        if self._table:
            await self._table.close()
            self._table = None
            self._table_task = None
