"""Entity representing a Sonos Move battery level."""
import logging
from typing import Any, Dict, Optional

from pysonos.core import SoCo
from pysonos.exceptions import SoCoException

from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE, STATE_UNKNOWN
from homeassistant.core import Event, callback
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from .const import (
    DATA_SONOS,
    DOMAIN as SONOS_DOMAIN,
    SCAN_INTERVAL,
    SONOS_DISCOVERY_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

ATTR_BATTERY_LEVEL = "battery_level"
ATTR_BATTERY_CHARGING = "charging"
ATTR_BATTERY_POWERSOURCE = "power_source"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    def _async_create_entities(event: Event):
        soco = event.data.get("soco")
        if soco and soco.uid not in hass.data[DATA_SONOS].battery_entities:
            hass.data[DATA_SONOS].battery_entities[soco.uid] = None
            hass.async_add_executor_job(_discover_battery, hass, soco)

    def _discover_battery(hass, soco):
        battery_info = SonosBatteryEntity.fetch(soco)
        if battery_info is not None:
            hass.add_job(async_add_entities, [SonosBatteryEntity(soco, battery_info)])

    hass.bus.async_listen(SONOS_DISCOVERY_UPDATE, _async_create_entities)

    # create any entities for devices that exist already
    for uid, soco in hass.data[DATA_SONOS].discovered.items():
        if uid not in hass.data[DATA_SONOS].battery_entities:
            hass.data[DATA_SONOS].battery_entities[soco.uid] = None
            hass.async_add_executor_job(_discover_battery, hass, soco)


class SonosBatteryEntity(Entity):
    """Representation of a Sonos Battery entity."""

    def __init__(self, soco: SoCo, battery_info: Dict[str, Any]):
        """Initialize a SonosBatteryEntity."""
        self._soco = soco
        self._battery_info = battery_info
        self._available = True

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
        cancel_timer = self.hass.helpers.event.async_track_time_interval(
            self.update, SCAN_INTERVAL
        )
        self.async_on_remove(cancel_timer)

        self.hass.data[DATA_SONOS].battery_entities[self.unique_id] = self

    async def async_seen(self, soco) -> None:
        """Record that this player was seen right now."""
        self._soco = soco

        self.async_write_ha_state()

    @callback
    def async_unseen(self, now=None):
        """Make this player unavailable when it was not seen recently."""
        self._available = False

        self.async_write_ha_state()

    # Identification of this Entity
    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._soco.uid + "-battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        speaker_info = self.hass.data[DATA_SONOS].speaker_info[self._soco.uid]
        return speaker_info["zone_name"] + " Battery"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return information about the device."""
        speaker_info = self.hass.data[DATA_SONOS].speaker_info[self._soco.uid]
        return {
            "identifiers": {(SONOS_DOMAIN, self._soco.uid)},
            "name": speaker_info["zone_name"],
            "model": speaker_info["model_name"].replace("Sonos ", ""),
            "sw_version": speaker_info["software_version"],
            "connections": {(dr.CONNECTION_NETWORK_MAC, speaker_info["mac_address"])},
            "manufacturer": "Sonos",
            "suggested_area": speaker_info["zone_name"],
        }

    @property
    def device_class(self) -> str:
        """Return the entity's device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement."""
        return PERCENTAGE

    # Update the current state
    def update(self, event=None):
        """Poll the device for the current state."""
        if not self.available:
            # wait for the Sonos device to come back online
            return
        battery_info = SonosBatteryEntity.fetch(self._soco)
        if battery_info is not None:
            self._battery_info = battery_info
            self.schedule_update_ha_state()

    # Current state
    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self._soco.uid in self.hass.data[DATA_SONOS].seen_timers

    @property
    def battery_level(self) -> int:
        """Return the battery level."""
        return self._battery_info.get("Level", 0)

    @property
    def power_source(self) -> str:
        """Return the name of the power source.

        Observed to be either BATTERY or SONOS_CHARGING_RING or USB_POWER.
        """
        return self._battery_info.get("PowerSource", STATE_UNKNOWN)

    @property
    def charging(self) -> bool:
        """Return the charging status of this battery."""
        return self.power_source not in ("BATTERY", STATE_UNKNOWN)

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return icon_for_battery_level(self.battery_level, self.charging)

    @property
    def state(self) -> Optional[int]:
        """Return the state of the sensor."""
        return self._battery_info.get("Level")

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            ATTR_BATTERY_CHARGING: self.charging,
            ATTR_BATTERY_POWERSOURCE: self.power_source,
        }
