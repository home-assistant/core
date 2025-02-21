"""Helper and coordinator for meross_scan."""

from __future__ import annotations

from datetime import timedelta

from meross_ha.controller.device import BaseDevice
from meross_ha.exceptions import DeviceTimeoutError, MerossError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN, HTTP_UPDATE_INTERVAL, MAX_ERRORS


class MerossDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Manages polling for state changes from the device."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, device: BaseDevice
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{device.device_info.dev_name}",
            update_interval=timedelta(seconds=HTTP_UPDATE_INTERVAL),
        )
        self.device = device
        self._error_count = 0

    async def _async_update_data(self) -> None:
        """Update the state of the device."""
        try:
            await self.device.async_handle_update()
            self._update_success(True)
        except DeviceTimeoutError as e:
            self._update_error_count()
            if self._error_count >= MAX_ERRORS:
                self._update_success(False)
            _LOGGER.warning("Device update timed out")
            raise UpdateFailed("Timeout") from e
        except MerossError as e:
            _LOGGER.error(f"Device connection error: {e!r}")
            raise UpdateFailed("Device connect error") from e

    def _update_success(self, success: bool) -> None:
        """Update the success state."""
        self.last_update_success = success
        self._error_count = 0 if success else self._error_count

    def _update_error_count(self) -> None:
        """Increment the error count."""
        self._error_count += 1
