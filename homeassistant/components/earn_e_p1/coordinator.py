"""DataUpdateCoordinator for the EARN-E P1 Meter integration."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from earn_e_p1 import EarnEP1Device, EarnEP1Listener

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
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
            # Each packet postpones the scheduled refresh, so it only runs once
            # the meter has gone silent. Scheduled refreshes can fire up to a
            # second early, hence the margin over the timeout.
            update_interval=NO_DATA_TIMEOUT + timedelta(seconds=1),
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

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Serve cached data while packets arrive, fail once the meter is silent."""
        timeout = NO_DATA_TIMEOUT.total_seconds()
        if (
            self._last_packet is None
            or self.hass.loop.time() - self._last_packet >= timeout
        ):
            raise UpdateFailed(
                f"No data received from {self.host} for {timeout:.0f} seconds"
            )
        return self.data

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
        if not self.last_update_success:
            _LOGGER.info("Device at %s is available", self.host)
        # Listeners run synchronously from async_set_updated_data and read this.
        self.data_complete = device.data_complete
        self.async_set_updated_data(device.data)

    def start(self) -> None:
        """Register with the shared listener."""
        self._listener.register(self.host, self._handle_update)

    def stop(self) -> None:
        """Unregister from the shared listener."""
        self._listener.unregister(self.host)
