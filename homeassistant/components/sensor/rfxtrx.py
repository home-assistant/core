"""
homeassistant.components.sensor.rfxtrx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shows sensor values from RFXtrx sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rfxtrx/
"""
import logging
from collections import OrderedDict

from homeassistant.const import (TEMP_CELCIUS)
from homeassistant.helpers.entity import Entity
import homeassistant.components.rfxtrx as rfxtrx
from homeassistant.util import slugify

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
    """ Setup the RFXtrx platform. """
    from RFXtrx import SensorEvent

    def sensor_update(event):
        """ Callback for sensor updates from the RFXtrx gateway. """
        if isinstance(event, SensorEvent):
            entity_id = slugify(event.device.id_string.lower())

            # Add entity if not exist and the automatic_add is True
            if entity_id not in rfxtrx.RFX_DEVICES:
                automatic_add = config.get('automatic_add', True)
                if automatic_add:
                    _LOGGER.info("Automatic add %s rfxtrx.sensor", entity_id)
                    new_sensor = RfxtrxSensor(event)
                    rfxtrx.RFX_DEVICES[entity_id] = new_sensor
                    add_devices_callback([new_sensor])
            else:
                _LOGGER.debug(
                    "EntityID: %s sensor_update",
                    entity_id,
                )
                rfxtrx.RFX_DEVICES[entity_id].event = event

    if sensor_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(sensor_update)


class RfxtrxSensor(Entity):
    """ Represents a RFXtrx sensor. """

    def __init__(self, event):
        self.event = event
        self._unit_of_measurement = None
        self._data_type = None
        for data_type in DATA_TYPES:
            if data_type in self.event.values:
                self._unit_of_measurement = DATA_TYPES[data_type]
                self._data_type = data_type
                break

        id_string = int(event.device.id_string.replace(":", ""), 16)
        self._name = "{} {} ({})".format(self._data_type,
                                         self.event.device.type_string,
                                         id_string)

    def __str__(self):
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        if self._data_type:
            return self.event.values[self._data_type]
        return None

    @property
    def name(self):
        """ Get the name of the sensor. """
        return self._name

    @property
    def device_state_attributes(self):
        return self.event.values

    @property
    def unit_of_measurement(self):
        """ Unit this state is expressed in. """
        return self._unit_of_measurement
