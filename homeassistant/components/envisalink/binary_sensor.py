"""Support for Envisalink zone states- represented as binary sensors."""

import datetime
import logging
from typing import Any, override

from pyenvisalink import EnvisalinkAlarmPanel

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_LAST_TRIP_TIME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import EnvisalinkConfigEntry
from .const import (
    CONF_ZONE_NUMBER,
    CONF_ZONENAME,
    CONF_ZONETYPE,
    SIGNAL_ZONE_UPDATE,
    SUBENTRY_TYPE_ZONE,
)
from .entity import EnvisalinkEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnvisalinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Envisalink binary sensor entities from a config entry."""
    controller = entry.runtime_data

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE):
        zone_number = subentry.data[CONF_ZONE_NUMBER]
        entity = EnvisalinkBinarySensor(
            zone_number,
            subentry.data[CONF_ZONENAME],
            subentry.data[CONF_ZONETYPE],
            controller.alarm_state["zone"][zone_number],
            controller,
        )
        async_add_entities([entity], config_subentry_id=subentry.subentry_id)


class EnvisalinkBinarySensor(EnvisalinkEntity, BinarySensorEntity):
    """Representation of an Envisalink binary sensor."""

    def __init__(
        self,
        zone_number: int,
        zone_name: str,
        zone_type: BinarySensorDeviceClass,
        info: dict[str, Any],
        controller: EnvisalinkAlarmPanel,
    ) -> None:
        """Initialize the binary_sensor."""
        self._attr_device_class = zone_type
        self._zone_number = zone_number

        _LOGGER.debug("Setting up zone: %s", zone_name)
        super().__init__(zone_name, info, controller)

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ZONE_UPDATE, self.async_update_callback
            )
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attr: dict[str, Any] = {}

        # The Envisalink library returns a "last_fault" value that's the
        # number of seconds since the last fault, up to a maximum of 327680
        # seconds (65536 5-second ticks).
        #
        # We don't want the HA event log to fill up with a bunch of no-op
        # "state changes" that are just that number ticking up once per poll
        # interval, so we subtract it from the current second-accurate time
        # unless it is already at the maximum value, in which case we set it
        # to None since we can't determine the actual value.
        seconds_ago = self._info["last_fault"]
        if seconds_ago < 65536 * 5:
            now = dt_util.now().replace(microsecond=0)
            delta = datetime.timedelta(seconds=seconds_ago)
            last_trip_time = (now - delta).isoformat()
        else:
            last_trip_time = None

        attr[ATTR_LAST_TRIP_TIME] = last_trip_time

        # Expose the zone number as an attribute to allow
        # for easier entity to zone mapping (e.g. to bypass
        # the zone).
        attr["zone"] = self._zone_number

        return attr

    @property
    @override
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self._info["status"]["open"]

    @callback
    def async_update_callback(self, zone):
        """Update the zone's state, if needed."""
        if zone is None or int(zone) == self._zone_number:
            self.async_write_ha_state()
