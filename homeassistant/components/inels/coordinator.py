"""iNELS data update coordinator."""
from __future__ import annotations

from datetime import timedelta

from inelsmqtt.devices import Device

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

SCAN_INTERVAL = 5


class InelsDeviceUpdateCoordinator(DataUpdateCoordinator[Device]):
    """Coordinator to manage data for specific iNELS devices."""

    def __init__(self, hass: HomeAssistant, *, device: Device) -> None:
        """Initialize device coordinator."""
        self.device = device
        self._exception: Exception | None = None

        super().__init__(
            hass,
            LOGGER,
            name=f"Update coordinator for {device}",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    @property
    def type(self) -> str:
        """Type of the coordinator entity."""

    @callback
    def _exception_callback(self, exc: Exception) -> None:
        """Schedule handling exception in HA."""
        self.hass.async_create_task(self._handle_exception(exc))

    async def set_broker_available(self, available: bool) -> None:
        """Set status of broker."""
        if available != self.last_update_success:
            if not available:
                self.last_update_success = False
            await self.async_request_refresh()

    async def _handle_exception(self, exc: Exception) -> None:
        """Handle discovery exceptions."""
        self._exception = exc

        LOGGER.debug(
            "Observation failed for %s trying again", self.device, exc_info=exc
        )

        self.update_interval = timedelta(seconds=5)
        await self.async_request_refresh()

    async def _async_update_data(self) -> Device:
        """Fetch data from the broker for a specific device."""
        try:
            if self._exception:
                exc = self._exception
                self._exception = None
                raise exc
        except Exception as err:
            raise UpdateFailed(f"Error communicating with broker: {err}.") from err

        if not self.data or not self.last_update_success:
            try:
                await self.hass.async_add_executor_job(self.device.get_value)
            except Exception as err:
                raise UpdateFailed(f"Error communicating with broker: {err}.") from err

            # reset update interval
            self.update_interval = timedelta(seconds=SCAN_INTERVAL)

        return self.device
