"""The IntelliFire integration."""
from __future__ import annotations

from datetime import timedelta

from pyflume import FlumeData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN

NOTIFICATION_SCAN_INTERVAL = timedelta(minutes=1)
DEVICE_SCAN_INTERVAL = timedelta(minutes=1)


class FlumeDeviceDataUpdateCoordinator(DataUpdateCoordinator[object]):
    """Data update coordinator for an individual flume device."""

    def __init__(
        self, hass: HomeAssistant, flume_auth, device_id, device_timezone, http_session
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=DEVICE_SCAN_INTERVAL,
        )

        self.flume_device = FlumeData(
            flume_auth,
            device_id,
            device_timezone,
            scan_interval=DEVICE_SCAN_INTERVAL,
            update_on_init=False,
            http_session=http_session,
        )

    async def _async_update_data(self):
        """Get the latest data from the Flume."""
        _LOGGER.debug("Updating Flume data")
        try:
            await self.hass.async_add_executor_job(self.flume_device.update_force)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
        _LOGGER.debug(
            "Flume update details: %s",
            {
                "values": self.flume_device.values,
                "query_payload": self.flume_device.query_payload,
            },
        )
