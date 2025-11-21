"""Data update coordinator for Marstek devices."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pymarstek import MarstekUDPClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_UDP_PORT

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class MarstekDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
            name=f"Marstek {device_ip}",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        _LOGGER.debug(
            "Device %s polling coordinator started, interval: %ss",
            device_ip,
            SCAN_INTERVAL.total_seconds(),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data using library's get_device_status method."""
        _LOGGER.debug("Start polling device: %s", self.device_ip)

        if self.udp_client.is_polling_paused(self.device_ip):
            _LOGGER.debug(
                "Polling paused for device: %s, skipping update", self.device_ip
            )
            return self.data or {}

        try:
            # Use library method to get complete device status
            device_status = await self.udp_client.get_device_status(
                self.device_ip,
                port=DEFAULT_UDP_PORT,
                timeout=2.5,
                include_pv=True,
                delay_between_requests=2.0,
            )
        except (TimeoutError, OSError, ValueError) as err:
            _LOGGER.error("Device %s status request failed: %s", self.device_ip, err)
            # Return previous data on error
            return self.data or {}
        else:
            _LOGGER.debug(
                "Device %s poll done: SOC %s%%, Power %sW, Mode %s, Status %s",
                self.device_ip,
                device_status.get("battery_soc"),
                device_status.get("battery_power"),
                device_status.get("device_mode"),
                device_status.get("battery_status"),
            )
            return device_status
