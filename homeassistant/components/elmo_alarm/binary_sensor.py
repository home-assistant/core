"""Support for e-connect Elmo zone states - represented as binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    INPUT_TYPE,
    SIGNAL_INPUT_CHANGED,
    SIGNAL_ZONE_CHANGED,
    ZONE_TYPE,
    InputData,
    ZoneData,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the e-connect Elmo Alarm binary sensor devices."""
    if not discovery_info:
        return

    zones = discovery_info["zones"]
    inputs = discovery_info["inputs"]

    devices = []
    for zone in zones:
        device = ElmoBinarySensor(zone.zone_id, zone.zone_name, zone.state, ZONE_TYPE)
        devices.append(device)

    for inp in inputs:
        device = ElmoBinarySensor(inp.input_id, inp.input_name, inp.state, INPUT_TYPE)
        devices.append(device)

    async_add_entities(devices)


class ElmoBinarySensor(BinarySensorDevice):
    """Representation of an Ness alarm zone as a binary sensor."""

    def __init__(self, sensor_index, sensor_name, sensor_state, sensor_type):
        """Initialize the binary_sensor."""

        self._index = sensor_index
        self._name = sensor_name
        self._type = sensor_type
        self._state = sensor_state

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_ZONE_CHANGED, self._handle_zone_change
        )
        async_dispatcher_connect(
            self.hass, SIGNAL_INPUT_CHANGED, self._handle_input_change
        )

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state == 1

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._type

    @callback
    def _handle_zone_change(self, data: ZoneData):
        """Handle zone state update."""
        if self._index == data.zone_id and self._type == ZONE_TYPE:
            self._state = data.state
            self.async_schedule_update_ha_state()

    @callback
    def _handle_input_change(self, data: InputData):
        """Handle zone state update."""
        if self._index == data.input_id and self._type == INPUT_TYPE:
            self._state = data.state
            self.async_schedule_update_ha_state()
