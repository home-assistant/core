"""Data update coordinator for iaqualink."""

from collections.abc import Callable
import logging
from typing import Any

import httpx
from iaqualink.device import AqualinkDevice
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL_BY_SYSTEM_TYPE, UPDATE_INTERVAL_DEFAULT
from .utils import error_detail

_LOGGER = logging.getLogger(__name__)


class AqualinkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, AqualinkDevice]]):
    """Data coordinator for Aqualink systems."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, system: Any
    ) -> None:
        """Initialize the coordinator."""
        update_interval = UPDATE_INTERVAL_BY_SYSTEM_TYPE.get(
            system.NAME, UPDATE_INTERVAL_DEFAULT
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{system.serial}",
            update_interval=update_interval,
        )
        self.system = system
        self._previous_devices: set[str] = set()
        self._initialized: bool = False
        self.new_device_callbacks: list[Callable[[list[AqualinkDevice]], None]] = []

    def seed_previous_devices(self, device_names: set[str]) -> None:
        """Seed the previous devices set from the device registry."""
        self._previous_devices = device_names
        self._initialized = bool(device_names)

    async def _async_update_data(self) -> dict[str, AqualinkDevice]:
        """Refresh internal state for a system."""
        try:
            await self.system.update()
        except AqualinkServiceUnauthorizedException as err:
            raise ConfigEntryAuthFailed("Invalid credentials for iAquaLink") from err
        except AqualinkServiceThrottledException:
            _LOGGER.warning(
                "Rate limited by iAquaLink system %s, will retry later",
                self.system.serial,
            )
            return self.data or {}
        except (AqualinkServiceException, TimeoutError, httpx.HTTPError) as err:
            raise UpdateFailed(
                "Unable to update iAquaLink system "
                f"{self.system.serial}: {error_detail(err)}"
            ) from err
        if self.system.online is not True:
            raise UpdateFailed(f"iAquaLink system {self.system.serial} is offline")

        try:
            devices = await self.system.get_devices()
        except AqualinkServiceUnauthorizedException as err:
            raise ConfigEntryAuthFailed("Invalid credentials for iAquaLink") from err
        except (AqualinkServiceException, TimeoutError, httpx.HTTPError) as err:
            raise UpdateFailed(
                "Unable to retrieve devices for iAquaLink system "
                f"{self.system.serial}: {error_detail(err)}"
            ) from err

        current_device_names = set(devices)

        if self._initialized:
            if new_names := current_device_names - self._previous_devices:
                new_devices = [devices[name] for name in new_names]
                for callback in self.new_device_callbacks:
                    callback(new_devices)

            if stale_names := self._previous_devices - current_device_names:
                device_registry = dr.async_get(self.hass)
                for name in stale_names:
                    device_id = f"{self.system.serial}_{name}"
                    if device := device_registry.async_get_device(
                        identifiers={(DOMAIN, device_id)}
                    ):
                        device_registry.async_update_device(
                            device_id=device.id,
                            remove_config_entry_id=self.config_entry.entry_id,
                        )

        self._initialized = True
        self._previous_devices = current_device_names
        return devices
