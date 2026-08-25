"""Data update coordinator for Marstek devices."""

from datetime import timedelta
import logging
from typing import override

from aiomarstek import MarstekUDPClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .models import MarstekDeviceInfo

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

type MarstekConfigEntry = ConfigEntry[MarstekDataUpdateCoordinator]


class MarstekDataUpdateCoordinator(DataUpdateCoordinator[dict[str, object]]):
    """Per-device data update coordinator."""

    config_entry: MarstekConfigEntry
    device_info: MarstekDeviceInfo

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MarstekConfigEntry,
        udp_client: MarstekUDPClient,
    ) -> None:
        """Initialize the coordinator."""
        self.device_ip = config_entry.data[CONF_HOST]
        self.udp_client = udp_client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Marstek {self.device_ip}",
            update_interval=SCAN_INTERVAL,
        )
        _LOGGER.debug(
            "Device %s polling coordinator started, interval: %ss",
            self.device_ip,
            SCAN_INTERVAL.total_seconds(),
        )

    @override
    async def _async_setup(self) -> None:
        """Validate device availability and cache its device information."""
        try:
            device_info = await self.udp_client.get_device_info(self.device_ip)
        except (TimeoutError, OSError, TypeError) as err:
            raise ConfigEntryNotReady(
                f"Unable to connect to Marstek device at {self.device_ip}"
            ) from err

        if not isinstance(device_info, dict):
            raise ConfigEntryNotReady(
                f"Marstek device at {self.device_ip} returned invalid data"
            )

        normalized_device_info = MarstekDeviceInfo.from_response(
            device_info, self.device_ip
        )
        if not normalized_device_info.stable_id:
            raise ConfigEntryNotReady(
                f"Marstek device at {self.device_ip} did not provide a stable ID"
            )

        self.device_info = normalized_device_info

    @override
    async def _async_update_data(self) -> dict[str, object]:
        """Fetch device data from the Marstek client library."""
        _LOGGER.debug("Start polling device: %s", self.device_ip)
        current_data = self.data or {}

        try:
            if self.udp_client.is_polling_paused(self.device_ip):
                _LOGGER.debug(
                    "Polling paused for device: %s, skipping update", self.device_ip
                )
                return current_data

            return await self.udp_client.get_device_status(
                self.device_ip,
                previous_data=current_data,
            )
        except (TimeoutError, OSError, TypeError) as err:
            raise UpdateFailed(
                f"Unable to update Marstek device at {self.device_ip}"
            ) from err
