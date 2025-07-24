"""Coordinator for Powerfox integration."""

from __future__ import annotations

from powerfox import (
    Device,
    Powerfox,
    PowerfoxAuthenticationError,
    PowerfoxConnectionError,
    PowerfoxNoDataError,
    Poweropti,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type PowerfoxConfigEntry = ConfigEntry[list[PowerfoxDataUpdateCoordinator]]


class PowerfoxDataUpdateCoordinator(DataUpdateCoordinator[Poweropti]):
    """Class to manage fetching Powerfox data from the API."""

    config_entry: PowerfoxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PowerfoxConfigEntry,
        client: Powerfox,
        device: Device,
    ) -> None:
        """Initialize global Powerfox data updater."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device = device

    async def _async_update_data(self) -> Poweropti:
        """Fetch data from Powerfox API."""
        try:
            return await self.client.device(device_id=self.device.id)
        except PowerfoxAuthenticationError as err:
            raise ConfigEntryAuthFailed(err) from err
        except (PowerfoxConnectionError, PowerfoxNoDataError) as err:
            raise UpdateFailed(err) from err
