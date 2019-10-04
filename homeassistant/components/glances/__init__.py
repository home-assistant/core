"""The Glances component."""
from datetime import timedelta
import logging

from glances_api import Glances, exceptions

from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import DATA_UPDATED, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Configure Glances using config flow only."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Met as config entry."""
    client = GlancesData(hass, config_entry)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = client
    if not await client.async_setup():
        return False

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    del hass.data[DOMAIN]
    return True


class GlancesData:
    """Glances Client Object."""

    def __init__(self, hass, config_entry):
        """Initialize the Glances client."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = None
        self.unsub_timer = None
        self.available = False

    @property
    def host(self):
        """Return api host."""
        return self.config_entry.data[CONF_HOST]

    async def async_update(self):
        """Get the latest data from the Glances REST API."""
        try:
            await self.api.get_data()
            self.available = True
        except exceptions.GlancesApiError:
            _LOGGER.error("Unable to fetch data from Glances")
            self.available = False
        _LOGGER.debug("Glances Data updated")
        async_dispatcher_send(self.hass, DATA_UPDATED)

    async def async_setup(self):
        """Set up the Glances client."""
        try:
            self.api = GlancesClient(self.hass, **self.config_entry.data)
            await self.api.get_data()
            self.available = True
            _LOGGER.debug("Successfully connected to Glances")
        except exceptions.GlancesApiConnectionError:
            _LOGGER.debug("Can not connect to Glances")
            raise ConfigEntryNotReady
        self.add_options()
        self.set_scan_interval(self.config_entry.options[CONF_SCAN_INTERVAL])
        self.config_entry.add_update_listener(self.async_options_updated)
        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "sensor"
            )
        )

        return True

    def add_options(self):
        """Add options for Glances integration."""
        if not self.config_entry.options:
            options = {CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL}
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
            )

    def set_scan_interval(self, scan_interval):
        """Update scan interval."""

        async def refresh(event_time):
            """Get the latest data from Glances api."""
            await self.async_update()

        if self.unsub_timer is not None:
            self.unsub_timer()
        self.unsub_timer = async_track_time_interval(
            self.hass, refresh, timedelta(seconds=scan_interval)
        )

    @staticmethod
    async def async_options_updated(hass, entry):
        """Triggered by config entry options updates."""
        hass.data[DOMAIN][entry.entry_id].set_scan_interval(
            entry.options[CONF_SCAN_INTERVAL]
        )


class GlancesClient(Glances):
    """Represents a Glance api."""

    def __init__(
        self,
        hass,
        name,
        host,
        port,
        version,
        ssl,
        verify_ssl,
        username=None,
        password=None,
    ):
        """Initialize Glances api."""
        session = async_get_clientsession(hass, verify_ssl)
        super().__init__(
            hass.loop,
            session,
            host=host,
            port=port,
            version=version,
            username=username,
            password=password,
            ssl=ssl,
        )
