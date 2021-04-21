"""Entity representing a Sonos battery level."""
import contextlib
import logging
from typing import Any, Dict, Optional

from pysonos.core import SoCo
from pysonos.events_base import Event as SonosEvent
from pysonos.exceptions import SoCoException

from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from . import SonosData
from .const import (
    BATTERY_SCAN_INTERVAL,
    DATA_SONOS,
    SONOS_DISCOVERY_UPDATE,
    SONOS_PROPERTIES_UPDATE,
    SONOS_SEEN,
    SONOS_UNSEEN,
)
from .entity import SonosEntity

_LOGGER = logging.getLogger(__name__)

ATTR_BATTERY_LEVEL = "battery_level"
ATTR_BATTERY_CHARGING = "charging"
ATTR_BATTERY_POWERSOURCE = "power_source"

EVENT_CHARGING = {
    "CHARGING": True,
    "NOT_CHARGING": False,
}


def fetch_battery_info_or_none(soco: SoCo) -> Optional[Dict[str, Any]]:
    """Fetch battery_info from the given SoCo object.

    Returns None if the device doesn't support battery info
    or if the device is offline.
    """
    with contextlib.suppress(ConnectionError, TimeoutError, SoCoException):
        return soco.get_battery_info()


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    sonos_data = hass.data[DATA_SONOS]

    async def _async_create_entity(soco: SoCo) -> Optional[SonosBatteryEntity]:
        if battery_info := await hass.async_add_executor_job(
            fetch_battery_info_or_none, soco
        ):
            return SonosBatteryEntity(soco, sonos_data, battery_info)
        return None

    async def _async_create_entities(soco: SoCo):
        if entity := await _async_create_entity(soco):
            async_add_entities([entity])

    async_dispatcher_connect(hass, SONOS_DISCOVERY_UPDATE, _async_create_entities)

    entities = []
    # create any entities for devices that exist already
    for soco in sonos_data.discovered.values():
        if entity := await _async_create_entity(soco):
            entities.append(entity)

    if entities:
        async_add_entities(entities)


class SonosBatteryEntity(SonosEntity, Entity):
    """Representation of a Sonos Battery entity."""

    def __init__(self, soco: SoCo, sonos_data: SonosData, battery_info: Dict[str, Any]):
        """Initialize a SonosBatteryEntity."""
        super().__init__(soco, sonos_data)
        self._battery_info = battery_info

    async def async_added_to_hass(self) -> None:
        """Register polling callback when added to hass."""
        self.async_on_remove(
            self.hass.helpers.event.async_track_time_interval(
                self.update, BATTERY_SCAN_INTERVAL
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SONOS_SEEN}-{self.soco.uid}", self.async_seen
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SONOS_UNSEEN}-{self.soco.uid}", self.async_unseen
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_PROPERTIES_UPDATE}-{self.soco.uid}",
                self.async_update_battery_info,
            )
        )

    async def async_update_battery_info(self, event: SonosEvent = None) -> None:
        """Update battery info using the provided SonosEvent."""
        if event is None:
            return

        if (more_info := event.variables.get("more_info")) is None:
            return

        more_info_dict = dict(x.split(":") for x in more_info.split(","))

        is_charging = EVENT_CHARGING[more_info_dict["BattChg"]]
        if is_charging == self.charging:
            self._battery_info.update({"Level": int(more_info_dict["BattPct"])})
        else:
            if battery_info := await self.hass.async_add_executor_job(
                fetch_battery_info_or_none, self.soco
            ):
                self._battery_info = battery_info

        self.schedule_update_ha_state()

    async def async_seen(self, soco) -> None:
        """Record that this player was seen right now."""
        self.soco = soco
        self.async_write_ha_state()

    @callback
    def async_unseen(self, now=None):
        """Make this player unavailable when it was not seen recently."""
        self.async_write_ha_state()

    # Identification of this Entity
    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self.soco.uid}-battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        speaker_info = self.data.speaker_info[self.soco.uid]
        return f"{speaker_info['zone_name']} Battery"

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
        battery_info = fetch_battery_info_or_none(self.soco)
        if battery_info is not None:
            self._battery_info = battery_info
            self.schedule_update_ha_state()

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
