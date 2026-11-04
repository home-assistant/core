"""DataUpdateCoordinator for the EARN-E P1 Meter integration."""

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from earn_e_p1 import EarnEP1Device, EarnEP1Listener

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import EarnEP1ConfigEntry

_LOGGER = logging.getLogger(__name__)

# The meter sends a full telegram roughly every 60 seconds.
NO_DATA_TIMEOUT = timedelta(minutes=2)


class EarnEP1Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for the EARN-E P1 Meter."""

    config_entry: EarnEP1ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EarnEP1ConfigEntry,
        host: str,
        serial: str,
        listener: EarnEP1Listener,
        mac: str | None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
        )
        self.host = host
        self.serial = serial
        self.identifier = serial
        self.mac = mac
        self.model: str | None = None
        self.sw_version: str | None = None
        self.data_complete = False
        self._listener = listener
        self._last_packet: float | None = None
        self._unsub_watchdog: CALLBACK_TYPE | None = None

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Serve cached data on a manual refresh unless the device went silent."""
        if (
            self._last_packet is None
            or self.hass.loop.time() - self._last_packet
            >= NO_DATA_TIMEOUT.total_seconds()
        ):
            raise self._no_data_error()
        return self.data

    def _no_data_error(self) -> UpdateFailed:
        """Build the error raised when the device went silent."""
        return UpdateFailed(
            f"No data received from {self.host} for "
            f"{NO_DATA_TIMEOUT.total_seconds():.0f} seconds"
        )

    @callback
    def _arm_watchdog(self) -> None:
        """Restart the no-data timer."""
        self._cancel_watchdog()
        self._unsub_watchdog = async_call_later(
            self.hass, NO_DATA_TIMEOUT, self._handle_no_data
        )

    @callback
    def _cancel_watchdog(self) -> None:
        """Stop the no-data timer."""
        if self._unsub_watchdog is not None:
            self._unsub_watchdog()
            self._unsub_watchdog = None

    @callback
    def _handle_no_data(self, _now: datetime) -> None:
        """Mark the device unavailable after a full timeout without packets."""
        self._unsub_watchdog = None
        self.async_set_update_error(self._no_data_error())

    def _handle_update(self, device: EarnEP1Device, _raw: dict[str, Any]) -> None:
        """Handle data update from the listener."""
        if self.model != device.model or self.sw_version != device.sw_version:
            self.model = device.model
            self.sw_version = device.sw_version
            device_registry = dr.async_get(self.hass)
            if (
                device_entry := device_registry.async_get_device_by_identifier(
                    (DOMAIN, self.identifier), self.config_entry.entry_id
                )
            ) is not None:
                device_registry.async_update_device(
                    device_entry.id,
                    model=self.model,
                    sw_version=self.sw_version,
                )
        self._last_packet = self.hass.loop.time()
        self._arm_watchdog()
        if not self.last_update_success:
            _LOGGER.info("Device at %s is available", self.host)
        # Listeners run synchronously from async_set_updated_data and read this.
        self.data_complete = device.data_complete
        self.async_set_updated_data(device.data)

    def start(self) -> None:
        """Register with the shared listener."""
        self._listener.register(self.host, self._handle_update)
        self._arm_watchdog()

    def stop(self) -> None:
        """Unregister from the shared listener."""
        self._listener.unregister(self.host)
        self._cancel_watchdog()
