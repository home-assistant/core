"""
Support for RFXtrx sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rfxtrx/
"""
import logging
import voluptuous as vol

import homeassistant.components.rfxtrx as rfxtrx
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.components.rfxtrx import (
    ATTR_AUTOMATIC_ADD, ATTR_NAME,
    CONF_DEVICES, ATTR_DATA_TYPE, DATA_TYPES)

DEPENDENCIES = ['rfxtrx']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required("platform"): rfxtrx.DOMAIN,
    vol.Optional(CONF_DEVICES, default={}): vol.All(dict, rfxtrx.valid_sensor),
    vol.Optional(ATTR_AUTOMATIC_ADD, default=False):  cv.boolean,
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the RFXtrx platform."""
    # pylint: disable=too-many-locals
    from RFXtrx import SensorEvent
    sensors = []
    for packet_id, entity_info in config['devices'].items():
        event = rfxtrx.get_rfx_object(packet_id)
        device_id = "sensor_" + slugify(event.device.id_string.lower())
        if device_id in rfxtrx.RFX_DEVICES:
            continue
        _LOGGER.info("Add %s rfxtrx.sensor", entity_info[ATTR_NAME])

        sub_sensors = {}
        data_types = entity_info[ATTR_DATA_TYPE]
        if len(data_types) == 0:
            for data_type in DATA_TYPES:
                if data_type in event.values:
                    data_types = [data_type]
                    break
        for _data_type in data_types:
            new_sensor = RfxtrxSensor(event, entity_info[ATTR_NAME],
                                      _data_type)
            sensors.append(new_sensor)
            sub_sensors[_data_type] = new_sensor
        rfxtrx.RFX_DEVICES[device_id] = sub_sensors

    add_devices_callback(sensors)

    def sensor_update(event):
        """Callback for sensor updates from the RFXtrx gateway."""
        if not isinstance(event, SensorEvent):
            return

        device_id = "sensor_" + slugify(event.device.id_string.lower())

        if device_id in rfxtrx.RFX_DEVICES:
            sensors = rfxtrx.RFX_DEVICES[device_id]
            for key in sensors:
                sensors[key].event = event
            return

        # Add entity if not exist and the automatic_add is True
        if not config[ATTR_AUTOMATIC_ADD]:
            return

        pkt_id = "".join("{0:02x}".format(x) for x in event.data)
        _LOGGER.info("Automatic add rfxtrx.sensor: %s",
                     device_id)

        data_type = "Unknown"
        for _data_type in DATA_TYPES:
            if _data_type in event.values:
                data_type = _data_type
                break
        new_sensor = RfxtrxSensor(event, pkt_id, data_type)
        sub_sensors = {}
        sub_sensors[new_sensor.data_type] = new_sensor
        rfxtrx.RFX_DEVICES[device_id] = sub_sensors
        add_devices_callback([new_sensor])

    if sensor_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(sensor_update)


class RfxtrxSensor(Entity):
    """Representation of a RFXtrx sensor."""

    def __init__(self, event, name, data_type):
        """Initialize the sensor."""
        self.event = event
        self._name = name
        if data_type not in DATA_TYPES:
            data_type = "Unknown"
        self.data_type = data_type
        self._unit_of_measurement = DATA_TYPES[data_type]

    def __str__(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.data_type:
            return self.event.values[self.data_type]
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
