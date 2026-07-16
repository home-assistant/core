"""Data coordinator for NuHeat."""

import logging
from typing import override

from chemelex_nuheat import (
    NuHeatApiError,
    NuHeatAuthError,
    NuHeatClient,
    NuHeatDataError,
    Thermostat,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class NuHeatCoordinator(DataUpdateCoordinator[dict[str, Thermostat]]):
    """Poll and retain all thermostats belonging to the linked account."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: NuHeatClient
    ) -> None:
        """Initialize the NuHeat coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self._present_serials: set[str] = set()

    @override
    async def _async_update_data(self) -> dict[str, Thermostat]:
        try:
            thermostats = await self.api.list_thermostats()
        except NuHeatAuthError as err:
            raise ConfigEntryAuthFailed("NuHeat authorization expired") from err
        except (NuHeatApiError, NuHeatDataError) as err:
            raise UpdateFailed("Unable to update NuHeat thermostats") from err

        fresh = {item.serial_number: item for item in thermostats}
        self._present_serials = set(fresh)
        # Retain previously discovered devices when an otherwise successful
        # account response temporarily omits one of them.
        return {**(self.data or {}), **fresh}

    def is_thermostat_available(self, serial_number: str) -> bool:
        """Return cloud and device availability without removing entities."""
        thermostat = (self.data or {}).get(serial_number)
        return (
            self.last_update_success
            and serial_number in self._present_serials
            and thermostat is not None
            and thermostat.online
        )

    def async_update_thermostat(self, thermostat: Thermostat) -> None:
        """Apply state returned by a successful write."""
        data = dict(self.data or {})
        data[thermostat.serial_number] = thermostat
        self._present_serials.add(thermostat.serial_number)
        self.async_set_updated_data(data)
