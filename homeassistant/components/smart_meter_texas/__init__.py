"""The Smart Meter Texas integration."""

import logging
import ssl

from smart_meter_texas import Account, Client, ClientSSLContext
from smart_meter_texas.exceptions import (
    SmartMeterTexasAPIError,
    SmartMeterTexasAuthError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_COORDINATOR,
    DATA_SMART_METER,
    DEBOUNCE_COOLDOWN,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Meter Texas from a config entry."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    account = Account(username, password)

    client_ssl_context = ClientSSLContext()
    ssl_context = await client_ssl_context.get_ssl_context()

    smart_meter_texas_data = SmartMeterTexasData(hass, entry, account, ssl_context)
    try:
        await smart_meter_texas_data.client.authenticate()
    except SmartMeterTexasAuthError:
        _LOGGER.error("Username or password was not accepted")
        return False
    except TimeoutError as error:
        raise ConfigEntryNotReady from error

    await smart_meter_texas_data.setup()

    async def async_update_data():
        _LOGGER.debug("Fetching latest data")
        await smart_meter_texas_data.read_meters()
        return smart_meter_texas_data

    # Use a DataUpdateCoordinator to manage the updates. This is due to the
    # Smart Meter Texas API which takes around 30 seconds to read a meter.
    # This avoids Home Assistant from complaining about the component taking
    # too long to update.
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Smart Meter Texas",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=Debouncer(
            hass, _LOGGER, cooldown=DEBOUNCE_COOLDOWN, immediate=True
        ),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_SMART_METER: smart_meter_texas_data,
    }

    entry.async_create_background_task(
        hass, coordinator.async_refresh(), "smart_meter_texas-coordinator-refresh"
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


class SmartMeterTexasData:
    """Manages coordinatation of API data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        account: Account,
        ssl_context: ssl.SSLContext,
    ) -> None:
        """Initialize the data coordintator."""
        self._entry = entry
        self.account = account
        websession = aiohttp_client.async_get_clientsession(hass)
        self.client = Client(websession, account, ssl_context=ssl_context)
        self.meters: list = []

    async def setup(self):
        """Fetch all of the user's meters."""
        self.meters = await self.account.fetch_meters(self.client)
        _LOGGER.debug("Discovered %s meter(s)", len(self.meters))

    async def read_meters(self):
        """Read each meter."""
        for meter in self.meters:
            try:
                await meter.read_meter(self.client)
            except (SmartMeterTexasAPIError, SmartMeterTexasAuthError) as error:
                raise UpdateFailed(error) from error
        return self.meters


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
