"""Define a data update coordinator for Point."""

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

from pypoint import PointSession
from tempora.utc import fromtimestamp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import parse_datetime

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class PointDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Class to manage fetching Point data from the API."""

    def __init__(self, hass: HomeAssistant, point: PointSession) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.point = point
        self.device_updates: dict[str, datetime] = {}
        self._known_devices: set[str] = set()
        self._known_homes: set[str] = set()
        self.new_home_callback: Callable[[str], None] | None = None
        self.new_device_callbacks: list[Callable[[str], None]] = []
        self.data: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        if not await self.point.update():
            raise UpdateFailed("Failed to fetch data from Point")

        if new_homes := set(self.point.homes) - self._known_homes:
            _LOGGER.debug("Found new homes: %s", new_homes)
            for home_id in new_homes:
                if self.new_home_callback:
                    self.new_home_callback(home_id)
            self._known_homes.update(new_homes)

        device_ids = {device.device_id for device in self.point.devices}
        if new_devices := device_ids - self._known_devices:
            _LOGGER.debug("Found new devices: %s", new_devices)
            for device_id in new_devices:
                for callback in self.new_device_callbacks:
                    callback(device_id)
            self._known_devices.update(new_devices)

        for device in self.point.devices:
            last_updated = parse_datetime(device.last_update)
            if (
                not last_updated
                or device.device_id not in self.device_updates
                or self.device_updates[device.device_id] < last_updated
            ):
                self.device_updates[device.device_id] = last_updated or fromtimestamp(0)
                self.data[device.device_id] = {
                    k: await device.sensor(k)
                    for k in ("temperature", "humidity", "sound_pressure")
                }
        return self.data
