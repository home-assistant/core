"""Entity representing a Sonos Move battery level."""
import datetime
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from pysonos.core import SoCo
from pysonos.exceptions import SoCoException

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

if TYPE_CHECKING:  # Avoid recursive import loops
    from .media_player import SonosEntity

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = datetime.timedelta(seconds=10)

ATTR_BATTERY_LEVEL = "battery_level"
ATTR_BATTERY_CHARGING = "charging"
ATTR_BATTERY_POWERSOURCE = "power_source"


class SonosBatteryEntity(Entity):
    """Representation of a Sonos Battery entity.

    Defers connection status to parent SonosEntity.
    """

    def __init__(self, parent: "SonosEntity", soco: SoCo, battery_info: Dict[str, Any]):
        """Initialize a SonosBatteryEntity from a parent SonosEntity."""
        self._parent = parent
        self._soco = soco
        self._battery_info = battery_info
        self._timer = None

    @staticmethod
    def fetch(soco: SoCo) -> Optional[Dict[str, Any]]:
        """Fetch battery_info from the given SoCo object.

        Returns None if the device doesn't support battery info
        or if the device is offline.
        """
        try:
            return soco.get_battery_info()
        except (ConnectionError, TimeoutError, SoCoException):
            pass
        return None

    async def async_added_to_hass(self) -> None:
        """Register polling callback when added to hass."""
        if self._timer is None:
            self._timer = self._parent.hass.helpers.event.async_track_time_interval(
                self.update, SCAN_INTERVAL
            )

    # Identification of this Entity
    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._parent.unique_id + "-battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._parent.name + " Battery"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return information about the device."""
        return self._parent.device_info

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement."""
        return "%"

    # Update the current state
    def update(self, event=None):
        """Poll the device for the current state."""
        if self.available:
            # only poll if the Sonos device is online
            _LOGGER.debug("Starting to check battery_info on %s", self._soco)
            battery_info = SonosBatteryEntity.fetch(self._soco)
            if battery_info is not None:
                self._battery_info = battery_info
                self.schedule_update_ha_state()

    # Current state
    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self._parent.available

    @property
    def battery_level(self) -> int:
        """Return the battery level."""
        return self._battery_info.get("Level", 0)

    @property
    def power_source(self) -> str:
        """Return the name of the power source.

        Observed to be either BATTERY or SONOS_CHARGING_RING or USB_POWER.
        """
        return self._battery_info.get("PowerSource", "Unknown")

    @property
    def charging(self) -> bool:
        """Return the charging status of this battery."""
        return self.power_source != "BATTERY"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return icon_for_battery_level(self.battery_level, self.charging)

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self._battery_info.get("Level")

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attributes = {
            ATTR_BATTERY_CHARGING: self.charging,
            ATTR_BATTERY_LEVEL: self.battery_level,
            ATTR_BATTERY_POWERSOURCE: self.power_source,
        }
        return attributes
