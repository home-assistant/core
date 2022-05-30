"""The pylontech_rs485 integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .pylontech_stack import PylontechStack

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class PylontechCoordinator(DataUpdateCoordinator):
    """Coordinator class to collect data from battery."""

    def __init__(self, hass: HomeAssistant, port: str, baud: int) -> None:
        """Pylontech setup."""
        self._stack = PylontechStack(device=port, baud=baud)
        self._last_result = self._stack.update()
        self._hass = hass

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from Battery."""
        self._last_result = await self._hass.async_add_executor_job(
            self._stack.update()
        )
        # self._lastResult = await self._stack.update()

    def get_result(self):
        """Return result dict from last poll."""
        return self._last_result


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up pylontech_rs485 from a config entry."""
    # TOODOO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    coordinator = PylontechCoordinator(hass, port="/dev/ttyUSB0", baud=115200)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
