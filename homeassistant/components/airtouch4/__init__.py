"""The AirTouch4 integration."""
import logging

from airtouch4pyapi import AirTouch
from airtouch4pyapi.airtouch import AirTouchStatus

from homeassistant.components.climate import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AirTouch4 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    airtouch = AirTouch(host)
    await airtouch.UpdateInfo()
    info = airtouch.GetAcs()
    if not info:
        raise ConfigEntryNotReady
    coordinator = AirtouchDataUpdateCoordinator(hass, airtouch)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class AirtouchDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Airtouch data."""

    def __init__(self, hass, airtouch):
        """Initialize global Airtouch data updater."""
        self.airtouch = airtouch

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from Airtouch."""
        await self.airtouch.UpdateInfo()
        if self.airtouch.Status != AirTouchStatus.OK:
            raise UpdateFailed("Airtouch connection issue")
        return {
            "acs": [
                {"ac_number": ac.AcNumber, "is_on": ac.IsOn}
                for ac in self.airtouch.GetAcs()
            ],
            "groups": [
                {
                    "group_number": group.GroupNumber,
                    "group_name": group.GroupName,
                    "is_on": group.IsOn,
                }
                for group in self.airtouch.GetGroups()
            ],
        }
