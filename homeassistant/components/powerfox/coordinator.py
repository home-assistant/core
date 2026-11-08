"""Coordinator for Powerfox integration."""

from datetime import timedelta
from typing import override

from powerfox import (
    Device,
    DeviceReport,
    Powerfox,
    PowerfoxAuthenticationError,
    PowerfoxConnectionError,
    PowerfoxNoDataError,
    PowerfoxPrivacyError,
    Poweropti,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEVICE_LIST_SCAN_INTERVAL, DOMAIN, LOGGER, SCAN_INTERVAL

type PowerfoxCoordinator = (
    PowerfoxDataUpdateCoordinator | PowerfoxReportDataUpdateCoordinator
)
type PowerfoxConfigEntry = ConfigEntry[list[PowerfoxCoordinator]]


class PowerfoxApiCoordinator[T](DataUpdateCoordinator[T]):
    """Base coordinator handling errors shared by all Powerfox API calls."""

    config_entry: PowerfoxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PowerfoxConfigEntry,
        client: Powerfox,
        update_interval: timedelta,
    ) -> None:
        """Initialize shared Powerfox API coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> T:
        """Fetch data and normalize Powerfox errors."""
        try:
            return await self._async_fetch_data()
        except PowerfoxAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except PowerfoxConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from err

    async def _async_fetch_data(self) -> T:
        """Fetch data from the Powerfox API."""
        raise NotImplementedError


class PowerfoxDeviceListCoordinator(PowerfoxApiCoordinator[list[Device]]):
    """Coordinator tracking the devices of a Powerfox account."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PowerfoxConfigEntry,
        client: Powerfox,
    ) -> None:
        """Initialize the device list coordinator."""
        super().__init__(hass, config_entry, client, DEVICE_LIST_SCAN_INTERVAL)

    @override
    async def _async_fetch_data(self) -> list[Device]:
        """Fetch the device list from the Powerfox API."""
        try:
            return await self.client.all_devices()
        except PowerfoxNoDataError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_devices",
            ) from err


class PowerfoxBaseCoordinator[T](PowerfoxApiCoordinator[T]):
    """Base coordinator handling shared Powerfox device logic."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PowerfoxConfigEntry,
        client: Powerfox,
        device: Device,
    ) -> None:
        """Initialize shared Powerfox device coordinator."""
        super().__init__(hass, config_entry, client, SCAN_INTERVAL)
        self.device = device

    @override
    async def _async_update_data(self) -> T:
        """Fetch device data and normalize device specific Powerfox errors."""
        try:
            return await super()._async_update_data()
        except PowerfoxNoDataError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_data_error",
                translation_placeholders={"device_name": self.device.name},
            ) from err
        except PowerfoxPrivacyError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="privacy_error",
                translation_placeholders={"device_name": self.device.name},
            ) from err


class PowerfoxDataUpdateCoordinator(PowerfoxBaseCoordinator[Poweropti]):
    """Class to manage fetching Powerfox data from the API."""

    @override
    async def _async_fetch_data(self) -> Poweropti:
        """Fetch live device data from the Powerfox API."""
        return await self.client.device(device_id=self.device.id)


class PowerfoxReportDataUpdateCoordinator(PowerfoxBaseCoordinator[DeviceReport]):
    """Coordinator handling report data from the API."""

    @override
    async def _async_fetch_data(self) -> DeviceReport:
        """Fetch report data from the Powerfox API."""
        local_now = dt_util.now()
        return await self.client.report(
            device_id=self.device.id,
            year=local_now.year,
            month=local_now.month,
            day=local_now.day,
        )
