"""
Support for RFXtrx sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rfxtrx/
"""
import logging
from collections import OrderedDict
import voluptuous as vol

import homeassistant.components.rfxtrx as rfxtrx
from homeassistant.const import TEMP_CELSIUS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify
from homeassistant.components.rfxtrx import (
    ATTR_AUTOMATIC_ADD, ATTR_NAME,
    CONF_DEVICES, ATTR_DATA_TYPE)

DEPENDENCIES = ['rfxtrx']

DATA_TYPES = OrderedDict([
    ('Temperature', TEMP_CELSIUS),
    ('Humidity', '%'),
    ('Barometer', ''),
    ('Wind direction', ''),
    ('Rain rate', ''),
    ('Energy usage', 'W'),
    ('Total usage', 'W')])
_LOGGER = logging.getLogger(__name__)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_NAME, default=None): cv.string,
    vol.Optional(ATTR_DATA_TYPE, default=[]):
        vol.All(cv.ensure_list, [vol.In(DATA_TYPES.keys())]),
})


def _valid_sensor(value):
    """Validate a dictionary of devices definitions."""
    config = OrderedDict()
    for key, device in value.items():
        # Still accept old configuration
        if 'packetid' in device.keys():
            print(key, device.keys(), device, config)
            msg = 'You are using an outdated configuration of the rfxtrx ' +\
                  'sensor, {}. Your new config should be:\n{}: \n\t name:{}\n'\
                  .format(key, device.get('packetid'),
                          device.get(ATTR_NAME, 'sensor_name'))
            _LOGGER.warning(msg)
            key = device.get('packetid')
            device.pop('packetid')
        try:
            key = rfxtrx.validate_packetid(key)
            config[key] = DEVICE_SCHEMA(device)
            if not config[key][ATTR_NAME]:
                config[key][ATTR_NAME] = key
        except vol.MultipleInvalid as ex:
            raise vol.Invalid('Rfxtrx sensor {} is invalid: {}'
                              .format(key, ex))
    return config


PLATFORM_SCHEMA = vol.Schema({
    vol.Required("platform"): rfxtrx.DOMAIN,
    vol.Required(CONF_DEVICES): vol.All(dict, _valid_sensor),
    vol.Optional(ATTR_AUTOMATIC_ADD, default=False):  cv.boolean,
}, extra=vol.ALLOW_EXTRA)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the RFXtrx platform."""
    from RFXtrx import SensorEvent

    sensors = []
    for packet_id, entity_info in config['devices'].items():
        event = rfxtrx.get_rfx_object(packet_id)
        device_id = "sensor_" + slugify(event.device.id_string.lower())

        if device_id in rfxtrx.RFX_DEVICES:
            continue
        _LOGGER.info("Add %s rfxtrx.sensor", entity_info[ATTR_NAME])
        sub_sensors = {}
        for _data_type in cv.ensure_list(entity_info[ATTR_DATA_TYPE]):
            new_sensor = RfxtrxSensor(event, entity_info[ATTR_NAME],
                                      _data_type)
            sensors.append(new_sensor)
            sub_sensors[_data_type] = new_sensor
        rfxtrx.RFX_DEVICES[slugify(device_id)] = sub_sensors

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
        if config[ATTR_AUTOMATIC_ADD]:
            pkt_id = "".join("{0:02x}".format(x) for x in event.data)
            entity_name = "%s : %s" % (device_id, pkt_id)
            _LOGGER.info(
                "Automatic add rfxtrx.sensor: (%s : %s)",
                device_id,
                pkt_id)

            new_sensor = RfxtrxSensor(event, entity_name)
            sub_sensors = {}
            sub_sensors[new_sensor.data_type] = new_sensor
            rfxtrx.RFX_DEVICES[device_id] = sub_sensors
            add_devices_callback([new_sensor])

    if sensor_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(sensor_update)


class RfxtrxSensor(Entity):
    """Representation of a RFXtrx sensor."""

    def __init__(self, event, name, data_type=None):
        """Initialize the sensor."""
        self.event = event
        self._unit_of_measurement = None
        self.data_type = None
        self._name = name
        if data_type:
            self.data_type = data_type
            self._unit_of_measurement = DATA_TYPES[data_type]
            return
        for data_type in DATA_TYPES:
            if data_type in self.event.values:
                self._unit_of_measurement = DATA_TYPES[data_type]
                self.data_type = data_type
                break

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
