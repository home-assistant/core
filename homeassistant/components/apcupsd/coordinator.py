"""Support for APCUPSd via its Network Information Server (NIS)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Final

import aioapcaccess

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    REQUEST_REFRESH_DEFAULT_IMMEDIATE,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONNECTION_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL: Final = timedelta(seconds=60)
REQUEST_REFRESH_COOLDOWN: Final = 5

type APCUPSdConfigEntry = ConfigEntry[APCUPSdCoordinator]


class APCUPSdData(dict[str, str]):
    """Store data about an APCUPSd and provide a few helper methods for easier accesses."""

    @property
    def name(self) -> str | None:
        """Return the name of the UPS, if available."""
        return self.get("UPSNAME")

    @property
    def model(self) -> str | None:
        """Return the model of the UPS, if available."""
        # Different UPS models may report slightly different keys for model, here we
        # try them all.
        return self.get("APCMODEL") or self.get("MODEL")

    @property
    def serial_no(self) -> str | None:
        """Return the unique serial number of the UPS, if available."""
        sn = self.get("SERIALNO")
        # We had user reports that some UPS models simply return "Blank" as serial number, in
        # which case we fall back to `None` to indicate that it is actually not available.
        return None if sn == "Blank" else sn


class APCUPSdCoordinator(DataUpdateCoordinator[APCUPSdData]):
    """Store and coordinate the data retrieved from APCUPSd for all sensors.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    config_entry: APCUPSdConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: APCUPSdConfigEntry,
        host: str,
        port: int,
    ) -> None:
        """Initialize the data object."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=REQUEST_REFRESH_COOLDOWN,
                immediate=REQUEST_REFRESH_DEFAULT_IMMEDIATE,
            ),
        )
        self._host = host
        self._port = port

    @property
    def unique_device_id(self) -> str:
        """Return a unique ID of the device, which is the serial number (if available) or the config entry ID."""
        return self.data.serial_no or self.config_entry.entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the DeviceInfo of this APC UPS, if serial number is available."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_device_id)},
            model=self.data.model,
            manufacturer="APC",
            name=self.data.name or "APC UPS",
            hw_version=self.data.get("FIRMWARE"),
            sw_version=self.data.get("VERSION"),
        )

    async def _async_update_data(self) -> APCUPSdData:
        """Fetch the latest status from APCUPSd.

        Note that the result dict uses upper case for each resource, where our
        integration uses lower cases as keys internally.
        """
        async with asyncio.timeout(CONNECTION_TIMEOUT):
            try:
                data = await aioapcaccess.request_status(self._host, self._port)
                return APCUPSdData(data)
            except (OSError, asyncio.IncompleteReadError) as error:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                ) from error
