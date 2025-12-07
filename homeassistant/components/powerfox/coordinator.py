"""Coordinator for Powerfox integration."""

from __future__ import annotations

from datetime import datetime

from powerfox import (
    Device,
    DeviceReport,
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
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type PowerfoxCoordinator = (
    "PowerfoxDataUpdateCoordinator" | "PowerfoxReportDataUpdateCoordinator"
)
type PowerfoxConfigEntry = ConfigEntry[list[PowerfoxCoordinator]]


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


class PowerfoxReportDataUpdateCoordinator(DataUpdateCoordinator[DeviceReport]):
    """Coordinator handling report data from the API."""

    config_entry: PowerfoxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PowerfoxConfigEntry,
        client: Powerfox,
        device: Device,
    ) -> None:
        """Initialize Powerfox report data updater."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device = device

    async def _async_update_data(self) -> DeviceReport:
        """Fetch report data from the Powerfox API."""
        try:
            local_now = datetime.now(
                tz=dt_util.get_time_zone(self.hass.config.time_zone)
            )
            return await self.client.report(
                device_id=self.device.id,
                year=local_now.year,
                month=local_now.month,
                day=local_now.day,
            )
        except PowerfoxAuthenticationError as err:
            raise ConfigEntryAuthFailed(err) from err
        except (PowerfoxConnectionError, PowerfoxNoDataError) as err:
            raise UpdateFailed(err) from err
