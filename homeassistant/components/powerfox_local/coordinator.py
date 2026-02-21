"""Coordinator for Powerfox Local integration."""

from __future__ import annotations

from powerfox import LocalResponse, PowerfoxConnectionError, PowerfoxLocal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type PowerfoxLocalConfigEntry = ConfigEntry[PowerfoxLocalDataUpdateCoordinator]


class PowerfoxLocalDataUpdateCoordinator(DataUpdateCoordinator[LocalResponse]):
    """Class to manage fetching Powerfox local data."""

    config_entry: PowerfoxLocalConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PowerfoxLocalConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = PowerfoxLocal(
            host=entry.data[CONF_HOST],
            api_key=entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
        )
        self.device_id: str = entry.data[CONF_API_KEY]
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> LocalResponse:
        """Fetch data from the local poweropti."""
        try:
            return await self.client.value()
        except PowerfoxConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
