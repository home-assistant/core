"""Support for Envisalink zone states- represented as binary sensors."""

from __future__ import annotations

import datetime
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_LAST_TRIP_TIME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import CONF_ZONENAME, CONF_ZONETYPE, DATA_EVL, SIGNAL_ZONE_UPDATE, ZONE_SCHEMA
from .entity import EnvisalinkEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Envisalink binary sensor entities."""
    if not discovery_info:
        return
    configured_zones = discovery_info["zones"]

    entities = []
    for zone_num in configured_zones:
        entity_config_data = ZONE_SCHEMA(configured_zones[zone_num])
        entity = EnvisalinkBinarySensor(
            hass,
            zone_num,
            entity_config_data[CONF_ZONENAME],
            entity_config_data[CONF_ZONETYPE],
            hass.data[DATA_EVL].alarm_state["zone"][zone_num],
            hass.data[DATA_EVL],
        )
        entities.append(entity)

    async_add_entities(entities)


class EnvisalinkBinarySensor(EnvisalinkEntity, BinarySensorEntity):
    """Representation of an Envisalink binary sensor."""

    def __init__(self, hass, zone_number, zone_name, zone_type, info, controller):
        """Initialize the binary_sensor."""
        self._zone_type = zone_type
        self._zone_number = zone_number

        _LOGGER.debug("Setting up zone: %s", zone_name)
        super().__init__(zone_name, info, controller)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ZONE_UPDATE, self.async_update_callback
            )
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = {}

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
    def is_on(self):
        """Return true if sensor is on."""
        return self._info["status"]["open"]

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._zone_type

    @callback
    def async_update_callback(self, zone):
        """Update the zone's state, if needed."""
        if zone is None or int(zone) == self._zone_number:
            self.async_write_ha_state()
