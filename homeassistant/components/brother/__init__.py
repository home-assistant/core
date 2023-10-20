"""The Brother component."""
from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging
import sys
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_CONFIG_ENTRY, DOMAIN, SNMP
from .utils import get_snmp_engine

if sys.version_info < (3, 12):
    from brother import Brother, BrotherSensors, SnmpError, UnsupportedModelError
else:
    BrotherSensors = Any

PLATFORMS = [Platform.SENSOR]

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Brother from a config entry."""
    if sys.version_info >= (3, 12):
        raise HomeAssistantError(
            "Brother Printer is not supported on Python 3.12. Please use Python 3.11."
        )
    host = entry.data[CONF_HOST]
    printer_type = entry.data[CONF_TYPE]

    snmp_engine = get_snmp_engine(hass)
    try:
        brother = await Brother.create(
            host, printer_type=printer_type, snmp_engine=snmp_engine
        )
    except (ConnectionError, SnmpError) as error:
        raise ConfigEntryNotReady from error

    coordinator = BrotherDataUpdateCoordinator(hass, brother)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(DATA_CONFIG_ENTRY, {})
    hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id] = coordinator
    hass.data[DOMAIN][SNMP] = snmp_engine

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)
        if not hass.data[DOMAIN][DATA_CONFIG_ENTRY]:
            hass.data[DOMAIN].pop(SNMP)
            hass.data[DOMAIN].pop(DATA_CONFIG_ENTRY)

    return unload_ok


class BrotherDataUpdateCoordinator(DataUpdateCoordinator[BrotherSensors]):
    """Class to manage fetching Brother data from the printer."""

    def __init__(self, hass: HomeAssistant, brother: Brother) -> None:
        """Initialize."""
        self.brother = brother

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> BrotherSensors:
        """Update data via library."""
        try:
            async with timeout(20):
                data = await self.brother.async_update()
        except (ConnectionError, SnmpError, UnsupportedModelError) as error:
            raise UpdateFailed(error) from error
        return data
