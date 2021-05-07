"""The Glances component."""
from datetime import timedelta
import logging

from glances_api import Glances, exceptions
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_VERSION,
    DATA_UPDATED,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VERSION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

GLANCES_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_SSL, default=False): cv.boolean,
            vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
            vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.In([2, 3]),
        }
    )
)

CONFIG_SCHEMA = vol.Schema(
    vol.All(cv.deprecated(DOMAIN), {DOMAIN: vol.All(cv.ensure_list, [GLANCES_SCHEMA])}),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Configure Glances using config flow only."""
    if DOMAIN in config:
        for entry in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                )
            )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Glances from config entry."""
    client = GlancesData(hass, config_entry)
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = client
    if not await client.async_setup():
        return False

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class GlancesData:
    """Get the latest data from Glances api."""

    def __init__(self, hass, config_entry):
        """Initialize the Glances data."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = None
        self.unsub_timer = None
        self.available = False

    @property
    def host(self):
        """Return client host."""
        return self.config_entry.data[CONF_HOST]

    async def async_update(self):
        """Get the latest data from the Glances REST API."""
        try:
            await self.api.get_data()
            self.available = True
        except exceptions.GlancesApiError:
            _LOGGER.error("Unable to fetch data from Glances")
            self.available = False
        _LOGGER.debug("Glances data updated")
        async_dispatcher_send(self.hass, DATA_UPDATED)

    async def async_setup(self):
        """Set up the Glances client."""
        try:
            self.api = get_api(self.hass, self.config_entry.data)
            await self.api.get_data()
            self.available = True
            _LOGGER.debug("Successfully connected to Glances")

        except exceptions.GlancesApiConnectionError as err:
            _LOGGER.debug("Can not connect to Glances")
            raise ConfigEntryNotReady from err

        self.add_options()
        self.set_scan_interval(self.config_entry.options[CONF_SCAN_INTERVAL])
        self.config_entry.async_on_unload(
            self.config_entry.add_update_listener(self.async_options_updated)
        )

        self.hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS)

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


def get_api(hass, entry):
    """Return the api from glances_api."""
    params = entry.copy()
    params.pop(CONF_NAME)
    verify_ssl = params.pop(CONF_VERIFY_SSL)
    session = async_get_clientsession(hass, verify_ssl)
    return Glances(hass.loop, session, **params)
