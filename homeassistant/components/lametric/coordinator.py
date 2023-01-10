"""DataUpdateCoordinator for the LaMatric integration."""
from __future__ import annotations

from demetriek import Device, LaMetricAuthenticationError, LaMetricDevice, LaMetricError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


class LaMetricDataUpdateCoordinator(DataUpdateCoordinator[Device]):
    """The LaMetric Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the LaMatric coordinator."""
        self.config_entry = entry
        self.lametric = LaMetricDevice(
            host=entry.data[CONF_HOST],
            api_key=entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
        )

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> Device:
        """Fetch device information of the LaMetric device."""
        try:
            return await self.lametric.device()
        except LaMetricAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except LaMetricError as ex:
            raise UpdateFailed(
                "Could not fetch device information from LaMetric device"
            ) from ex
