"""
Support for RFXtrx sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rfxtrx/
"""
import logging
from collections import OrderedDict

import homeassistant.components.rfxtrx as rfxtrx
from homeassistant.const import TEMP_CELCIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.components.rfxtrx import (
    ATTR_PACKETID, ATTR_NAME, ATTR_DATA_TYPE)

DEPENDENCIES = ['rfxtrx']

DATA_TYPES = OrderedDict([
    ('Temperature', TEMP_CELCIUS),
    ('Humidity', '%'),
    ('Barometer', ''),
    ('Wind direction', ''),
    ('Rain rate', ''),
    ('Energy usage', 'W'),
    ('Total usage', 'W')])
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the RFXtrx platform."""
    from RFXtrx import SensorEvent

    sensors = []
    for device_id, entity_info in config.get('devices', {}).items():
        if device_id in rfxtrx.RFX_DEVICES:
            continue
        _LOGGER.info("Add %s rfxtrx.sensor", entity_info[ATTR_NAME])
        event = rfxtrx.get_rfx_object(entity_info[ATTR_PACKETID])
        new_sensor = RfxtrxSensor(event, entity_info[ATTR_NAME],
                                  entity_info.get(ATTR_DATA_TYPE, None))
        rfxtrx.RFX_DEVICES[device_id] = new_sensor
        sensors.append(new_sensor)

    add_devices_callback(sensors)

    def sensor_update(event):
        """Callback for sensor updates from the RFXtrx gateway."""
        if not isinstance(event, SensorEvent):
            return

        device_id = "sensor_" + slugify(event.device.id_string.lower())

        if device_id in rfxtrx.RFX_DEVICES:
            rfxtrx.RFX_DEVICES[device_id].event = event
            return

        # Add entity if not exist and the automatic_add is True
        if config.get('automatic_add', True):
            pkt_id = "".join("{0:02x}".format(x) for x in event.data)
            entity_name = "%s : %s" % (device_id, pkt_id)
            _LOGGER.info(
                "Automatic add rfxtrx.sensor: (%s : %s)",
                device_id,
                pkt_id)

            new_sensor = RfxtrxSensor(event, entity_name)
            rfxtrx.RFX_DEVICES[device_id] = new_sensor
            add_devices_callback([new_sensor])

    if sensor_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(sensor_update)


class RfxtrxSensor(Entity):
    """Representation of a RFXtrx sensor."""

    def __init__(self, event, name, data_type=None):
        """Initialize the sensor."""
        self.event = event
        self._unit_of_measurement = None
        self._data_type = None
        self._name = name
        if data_type:
            self._data_type = data_type
            self._unit_of_measurement = DATA_TYPES[data_type]
            return
        for data_type in DATA_TYPES:
            if data_type in self.event.values:
                self._unit_of_measurement = DATA_TYPES[data_type]
                self._data_type = data_type
                break

    def __str__(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._data_type:
            return self.event.values[self._data_type]
        return None

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self.event.values

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement
