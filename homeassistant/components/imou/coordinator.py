"""Provides the Imou DataUpdateCoordinator."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_TIMEOUT, imou_device_identifier

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)

type ImouConfigEntry = ConfigEntry[ImouDataUpdateCoordinator]


class ImouDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for Imou devices."""

    config_entry: ImouConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        device_manager: ImouHaDeviceManager,
        config_entry: ImouConfigEntry,
    ) -> None:
        """Initialize the Imou data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ImouDataUpdateCoordinator",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
            always_update=True,
        )
        self._device_manager = device_manager
        self._devices_by_key: dict[str, ImouHaDevice] = {}
        self.new_device_callbacks: list[Callable[[list[ImouHaDevice]], None]] = []

    @property
    def devices(self) -> list[ImouHaDevice]:
        """Return the list of devices."""
        return list(self._devices_by_key.values())

    @property
    def device_manager(self) -> ImouHaDeviceManager:
        """Return the device manager."""
        return self._device_manager

    def get_device(self, device_key: str) -> ImouHaDevice | None:
        """Return the current device for device_key, if still on the account."""
        return self._devices_by_key.get(device_key)

    async def _async_update_data(self) -> None:
        """Update coordinator data."""
        async with asyncio.timeout(UPDATE_TIMEOUT):
            try:
                fresh_devices = await self._device_manager.async_get_devices()
                fresh_by_key = {
                    imou_device_identifier(device): device for device in fresh_devices
                }
                self._async_add_remove_devices(fresh_by_key)
                await asyncio.gather(
                    *[
                        self._device_manager.async_update_device_status(device)
                        for device in self._devices_by_key.values()
                    ],
                )
            except TimeoutError as err:
                raise UpdateFailed(f"Timeout while fetching data: {err}") from err
            except ImouException as err:
                raise UpdateFailed(f"Error updating Imou devices: {err}") from err

    def _async_add_remove_devices(self, fresh_by_key: dict[str, ImouHaDevice]) -> None:
        """Add new devices, remove devices no longer in the account."""
        if not self._devices_by_key:
            self._devices_by_key = fresh_by_key
            return

        current_keys = set(fresh_by_key)
        known_keys = set(self._devices_by_key)

        if current_keys == known_keys:
            return

        if removed_keys := known_keys - current_keys:
            _LOGGER.debug("Removed Imou device(s): %s", ", ".join(removed_keys))
            device_registry = dr.async_get(self.hass)
            for device_key in removed_keys:
                del self._devices_by_key[device_key]
                if device := device_registry.async_get_device(
                    identifiers={(DOMAIN, device_key)}
                ):
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )

        if new_keys := current_keys - known_keys:
            _LOGGER.debug("New Imou device(s) found: %s", ", ".join(new_keys))
            new_devices = []
            for device_key in new_keys:
                self._devices_by_key[device_key] = fresh_by_key[device_key]
                new_devices.append(fresh_by_key[device_key])
            for callback in self.new_device_callbacks:
                callback(new_devices)
