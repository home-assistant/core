"""The Smart Meter Texas integration."""
import asyncio
import logging

from smart_meter_texas import Account, Client
from smart_meter_texas.exceptions import SmartMeterTexasAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, SCAN_INTERVAL  # noqa: F401

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Smart Meter Texas component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Smart Meter Texas from a config entry."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    account = Account(username, password)
    smartmetertexas = SmartMeterTexasData(hass, entry, account)

    try:
        await smartmetertexas.client.authenticate()
        _LOGGER.debug("Successfully logged in")
    except SmartMeterTexasAuthError as error:
        _LOGGER.error("Error authenticating: %s", error)
        return False

    await smartmetertexas.setup()

    hass.data[DOMAIN][entry.entry_id] = smartmetertexas

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


class SmartMeterTexasData:
    """Manages coordinatation of API data updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, account: Account):
        """Initialize the data coordintator."""
        self._hass = hass
        self._entry = entry
        self.account = account
        websession = aiohttp_client.async_get_clientsession(hass)
        self.client = Client(websession, account)
        self.meters = []

    async def setup(self):
        """Fetch all of the user's meters."""
        try:
            self.meters = await self.account.fetch_meters(self.client)
        except SmartMeterTexasAuthError as error:
            _LOGGER.error("Error authenticating: %s", error)

        _LOGGER.debug("Discovered %s meter(s)", len(self.meters))

        if not self.meters:
            return False

        return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
