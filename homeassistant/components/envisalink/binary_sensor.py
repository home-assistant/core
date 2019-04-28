"""Support for Envisalink zone states- represented as binary sensors."""
import datetime
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import ATTR_LAST_TRIP_TIME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from . import (
    CONF_ZONENAME, CONF_ZONETYPE, DATA_EVL, SIGNAL_ZONE_UPDATE, ZONE_SCHEMA,
    EnvisalinkDevice)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Envisalink binary sensor devices."""
    configured_zones = discovery_info['zones']

    devices = []
    for zone_num in configured_zones:
        device_config_data = ZONE_SCHEMA(configured_zones[zone_num])
        device = EnvisalinkBinarySensor(
            hass,
            zone_num,
            device_config_data[CONF_ZONENAME],
            device_config_data[CONF_ZONETYPE],
            hass.data[DATA_EVL].alarm_state['zone'][zone_num],
            hass.data[DATA_EVL]
        )
        devices.append(device)

    async_add_entities(devices)


class EnvisalinkBinarySensor(EnvisalinkDevice, BinarySensorDevice):
    """Representation of an Envisalink binary sensor."""

    def __init__(self, hass, zone_number, zone_name, zone_type, info,
                 controller):
        """Initialize the binary_sensor."""
        self._zone_type = zone_type
        self._zone_number = zone_number

        _LOGGER.debug('Setting up zone: %s', zone_name)
        super().__init__(zone_name, info, controller)

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_ZONE_UPDATE, self._update_callback)

    @property
    def device_state_attributes(self):
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
        seconds_ago = self._info['last_fault']
        if seconds_ago < 65536 * 5:
            now = dt_util.now().replace(microsecond=0)
            delta = datetime.timedelta(seconds=seconds_ago)
            last_trip_time = (now - delta).isoformat()
        else:
            last_trip_time = None

        attr[ATTR_LAST_TRIP_TIME] = last_trip_time
        return attr

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._info['status']['open']

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._zone_type

    @callback
    def _update_callback(self, zone):
        """Update the zone's state, if needed."""
        if zone is None or int(zone) == self._zone_number:
            self.async_schedule_update_ha_state()
