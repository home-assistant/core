"""Support for Flo Water Monitor sensors."""

from typing import Any, Dict, List, Optional

from homeassistant.const import VOLUME_GALLONS
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as FLO_DOMAIN
from .device import FloDevice

DEPENDENCIES = ["flo"]

WATER_ICON = "mdi:water"
NAME_DAILY_USAGE = "Daily Water Counsumption"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flo sensors from config entry."""
    devices: List[FloDevice] = hass.data[FLO_DOMAIN]["devices"]
    async_add_entities([FloDailyUsageSensor(device) for device in devices], True)


class FloDailyUsageSensor(Entity):
    """Monitors the daily water usage."""

    def __init__(self, device):
        """Initialize the daily water usage sensor."""
        self._device: FloDevice = device
        self._state: float = None

    @property
    def unique_id(self) -> Optional[str]:
        """Return the unique id for the sensor."""
        return f"{self._device.mac_address}_daily_consumption"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return a device description for device registry."""
        return {
            "identifiers": {(FLO_DOMAIN, self._device.id)},
            "manufacturer": self._device.manufacturer,
            "model": self._device.model,
            "name": self._device.name,
            "sw_version": self._device.firmware_version,
        }

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._device.available

    @property
    def name(self) -> str:
        """Return the name for daily usage."""
        return NAME_DAILY_USAGE

    @property
    def icon(self) -> str:
        """Return the daily usage icon."""
        return WATER_ICON

    @property
    def state(self) -> Optional[float]:
        """Return the current daily usage."""
        if not self._device._consumption_today:
            return None
        return round(self._device._consumption_today, 1)

    @property
    def should_poll(self) -> bool:
        """Return the polling state."""
        return True

    @property
    def unit_of_measurement(self) -> str:
        """Return gallons as the unit measurement for water."""
        return VOLUME_GALLONS

    async def async_update(self) -> None:
        """Retrieve the latest daily usage."""
