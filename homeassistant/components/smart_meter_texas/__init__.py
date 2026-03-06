"""The Smart Meter Texas integration."""

import logging

from smart_meter_texas import Account
from smart_meter_texas.exceptions import SmartMeterTexasAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DATA_COORDINATOR, DATA_SMART_METER, DOMAIN
from .coordinator import SmartMeterTexasCoordinator, SmartMeterTexasData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Meter Texas from a config entry."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    account = Account(username, password)

    smart_meter_texas_data = SmartMeterTexasData(hass, account)
    try:
        await smart_meter_texas_data.client.authenticate()
    except SmartMeterTexasAuthError:
        _LOGGER.error("Username or password was not accepted")
        return False
    except TimeoutError as error:
        raise ConfigEntryNotReady from error

    await smart_meter_texas_data.setup()

    # Use a DataUpdateCoordinator to manage the updates. This is due to the
    # Smart Meter Texas API which takes around 30 seconds to read a meter.
    # This avoids Home Assistant from complaining about the component taking
    # too long to update.
    coordinator = SmartMeterTexasCoordinator(hass, entry, smart_meter_texas_data)

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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
