"""Data update coordinator for Marstek devices."""

from datetime import timedelta
import logging
from typing import Any, override

from aiomarstek import MarstekUDPClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class MarstekDataUpdateCoordinator(DataUpdateCoordinator):
    """Per-device data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        udp_client: MarstekUDPClient,
        device_ip: str,
    ) -> None:
        """Initialize the coordinator."""
        self.udp_client = udp_client
        self.device_ip = device_ip
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Marstek {device_ip}",
            update_interval=SCAN_INTERVAL,
        )
        _LOGGER.debug(
            "Device %s polling coordinator started, interval: %ss",
            device_ip,
            SCAN_INTERVAL.total_seconds(),
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch device data from the Marstek client library."""
        _LOGGER.debug("Start polling device: %s", self.device_ip)
        current_data = self.data or {}

        if self.udp_client.is_polling_paused(self.device_ip):
            _LOGGER.debug(
                "Polling paused for device: %s, skipping update", self.device_ip
            )
            return current_data

        return await self.udp_client.get_device_status(
            self.device_ip,
            previous_data=current_data,
        )
