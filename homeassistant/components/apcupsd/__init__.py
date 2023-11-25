"""Support for APCUPSd via its Network Information Server (NIS)."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import timedelta
import logging
from typing import Final

from apcaccess import status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    REQUEST_REFRESH_DEFAULT_IMMEDIATE,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "apcupsd"
PLATFORMS: Final = (Platform.BINARY_SENSOR, Platform.SENSOR)
UPDATE_INTERVAL: Final = timedelta(seconds=60)
REQUEST_REFRESH_COOLDOWN: Final = 5

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Use config values to set up a function enabling status retrieval."""
    host, port = config_entry.data[CONF_HOST], config_entry.data[CONF_PORT]
    coordinator = APCUPSdCoordinator(hass, host, port)

    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator for later uses.
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    # Forward the config entries to the supported platforms.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class APCUPSdCoordinator(DataUpdateCoordinator[OrderedDict[str, str]]):
    """Store and coordinate the data retrieved from APCUPSd for all sensors.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Initialize the data object."""
        super().__init__(
            hass,
            _LOGGER,
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
    def ups_name(self) -> str | None:
        """Return the name of the UPS, if available."""
        return self.data.get("UPSNAME")

    @property
    def ups_model(self) -> str | None:
        """Return the model of the UPS, if available."""
        # Different UPS models may report slightly different keys for model, here we
        # try them all.
        for model_key in ("APCMODEL", "MODEL"):
            if model_key in self.data:
                return self.data[model_key]
        return None

    @property
    def ups_serial_no(self) -> str | None:
        """Return the unique serial number of the UPS, if available."""
        return self.data.get("SERIALNO")

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the DeviceInfo of this APC UPS, if serial number is available."""
        if not self.ups_serial_no:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self.ups_serial_no)},
            model=self.ups_model,
            manufacturer="APC",
            name=self.ups_name if self.ups_name else "APC UPS",
            hw_version=self.data.get("FIRMWARE"),
            sw_version=self.data.get("VERSION"),
        )

    async def _async_update_data(self) -> OrderedDict[str, str]:
        """Fetch the latest status from APCUPSd.

        Note that the result dict uses upper case for each resource, where our
        integration uses lower cases as keys internally.
        """

        async with asyncio.timeout(10):
            try:
                raw = await self.hass.async_add_executor_job(
                    status.get, self._host, self._port
                )
                result: OrderedDict[str, str] = status.parse(raw)
                return result
            except OSError as error:
                raise UpdateFailed(error) from error
