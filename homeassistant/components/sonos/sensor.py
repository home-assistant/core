"""Entity representing a Sonos battery level."""
from __future__ import annotations

import contextlib
import datetime
import logging
from typing import Any

from pysonos.core import SoCo
from pysonos.events_base import Event as SonosEvent
from pysonos.exceptions import SoCoException

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity
from homeassistant.const import DEVICE_CLASS_BATTERY, PERCENTAGE, STATE_UNKNOWN
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.util import dt as dt_util

from . import SonosData
from .const import (
    BATTERY_SCAN_INTERVAL,
    DATA_SONOS,
    SONOS_DISCOVERY_UPDATE,
    SONOS_ENTITY_CREATED,
    SONOS_PROPERTIES_UPDATE,
)
from .entity import SonosEntity
from .speaker import SonosSpeaker

_LOGGER = logging.getLogger(__name__)

ATTR_BATTERY_LEVEL = "battery_level"
ATTR_BATTERY_CHARGING = "charging"
ATTR_BATTERY_POWERSOURCE = "power_source"

EVENT_CHARGING = {
    "CHARGING": True,
    "NOT_CHARGING": False,
}


def fetch_battery_info_or_none(soco: SoCo) -> dict[str, Any] | None:
    """Fetch battery_info from the given SoCo object.

    Returns None if the device doesn't support battery info
    or if the device is offline.
    """
    with contextlib.suppress(ConnectionError, TimeoutError, SoCoException):
        return soco.get_battery_info()
    return None


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Sonos from a config entry."""

    sonos_data = hass.data[DATA_SONOS]

    async def _async_create_entity(speaker: SonosSpeaker) -> SonosBatteryEntity | None:
        if battery_info := await hass.async_add_executor_job(
            fetch_battery_info_or_none, speaker.soco
        ):
            return SonosBatteryEntity(speaker, sonos_data, battery_info)
        return None

    async def _async_create_entities(speaker: SonosSpeaker):
        if entity := await _async_create_entity(speaker):
            async_add_entities([entity])
        else:
            async_dispatcher_send(
                hass, f"{SONOS_ENTITY_CREATED}-{speaker.soco.uid}", SENSOR_DOMAIN
            )

    async_dispatcher_connect(hass, SONOS_DISCOVERY_UPDATE, _async_create_entities)


class SonosBatteryEntity(SonosEntity, SensorEntity):
    """Representation of a Sonos Battery entity."""

    def __init__(
        self, speaker: SonosSpeaker, sonos_data: SonosData, battery_info: dict[str, Any]
    ) -> None:
        """Initialize a SonosBatteryEntity."""
        super().__init__(speaker, sonos_data)
        self._battery_info: dict[str, Any] = battery_info
        self._last_event: datetime.datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Register polling callback when added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self.hass.helpers.event.async_track_time_interval(
                self.async_update, BATTERY_SCAN_INTERVAL
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SONOS_PROPERTIES_UPDATE}-{self.soco.uid}",
                self.async_update_battery_info,
            )
        )
        async_dispatcher_send(
            self.hass, f"{SONOS_ENTITY_CREATED}-{self.soco.uid}", SENSOR_DOMAIN
        )

    async def async_update_battery_info(self, event: SonosEvent = None) -> None:
        """Update battery info using the provided SonosEvent."""
        if event is None:
            return

        if (more_info := event.variables.get("more_info")) is None:
            return

        more_info_dict = dict(x.split(":") for x in more_info.split(","))
        self._last_event = dt_util.utcnow()

        is_charging = EVENT_CHARGING[more_info_dict["BattChg"]]
        if is_charging == self.charging:
            self._battery_info.update({"Level": int(more_info_dict["BattPct"])})
        else:
            if battery_info := await self.hass.async_add_executor_job(
                fetch_battery_info_or_none, self.soco
            ):
                self._battery_info = battery_info

        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self.soco.uid}-battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.speaker.zone_name} Battery"

    @property
    def device_class(self) -> str:
        """Return the entity's device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement."""
        return PERCENTAGE

    async def async_update(self, event=None) -> None:
        """Poll the device for the current state."""
        if not self.available:
            # wait for the Sonos device to come back online
            return

        if (
            self._last_event
            and dt_util.utcnow() - self._last_event < BATTERY_SCAN_INTERVAL
        ):
            return

        if battery_info := await self.hass.async_add_executor_job(
            fetch_battery_info_or_none, self.soco
        ):
            self._battery_info = battery_info
            self.async_write_ha_state()

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
    def state(self) -> int | None:
        """Return the state of the sensor."""
        return self._battery_info.get("Level")

    @property
    def device_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            ATTR_BATTERY_CHARGING: self.charging,
            ATTR_BATTERY_POWERSOURCE: self.power_source,
        }
