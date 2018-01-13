"""
Tado component to create some sensors for each zone.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tado/
"""
import logging

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.components.tado import (DATA_TADO)
from homeassistant.const import (ATTR_ID)

_LOGGER = logging.getLogger(__name__)

ATTR_DATA_ID = 'data_id'
ATTR_DEVICE = 'device'
ATTR_NAME = 'name'
ATTR_ZONE = 'zone'

CLIMATE_SENSOR_TYPES = ['temperature', 'humidity', 'power',
                        'link', 'heating', 'tado mode', 'overlay']

HOT_WATER_SENSOR_TYPES = ['power', 'link', 'tado mode', 'overlay']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sensor platform."""
    tado = hass.data[DATA_TADO]

    try:
        zones = tado.get_zones()
    except RuntimeError:
        _LOGGER.error("Unable to get zone info from mytado")
        return

    sensor_items = []
    for zone in zones:
        if zone['type'] == 'HEATING':
            for variable in CLIMATE_SENSOR_TYPES:
                sensor_items.append(create_zone_sensor(
                    tado, zone, zone['name'], zone['id'],
                    variable))
        elif zone['type'] == 'HOT_WATER':
            for variable in HOT_WATER_SENSOR_TYPES:
                sensor_items.append(create_zone_sensor(
                    tado, zone, zone['name'], zone['id'],
                    variable
                ))

    me_data = tado.get_me()
    sensor_items.append(create_device_sensor(
        tado, me_data, me_data['homes'][0]['name'],
        me_data['homes'][0]['id'], "tado bridge status"))

    if sensor_items:
        add_devices(sensor_items, True)


def create_zone_sensor(tado, zone, name, zone_id, variable):
    """Create a zone sensor."""
    data_id = 'zone {} {}'.format(name, zone_id)

    tado.add_sensor(data_id, {
        ATTR_ZONE: zone,
        ATTR_NAME: name,
        ATTR_ID: zone_id,
        ATTR_DATA_ID: data_id
    })

    return TadoSensor(tado, name, zone_id, variable, data_id)


def create_device_sensor(tado, device, name, device_id, variable):
    """Create a device sensor."""
    data_id = 'device {} {}'.format(name, device_id)

    tado.add_sensor(data_id, {
        ATTR_DEVICE: device,
        ATTR_NAME: name,
        ATTR_ID: device_id,
        ATTR_DATA_ID: data_id
    })

    return TadoSensor(tado, name, device_id, variable, data_id)


class TadoSensor(Entity):
    """Representation of a tado Sensor."""

    def __init__(self, store, zone_name, zone_id, zone_variable, data_id):
        """Initialize of the Tado Sensor."""
        self._store = store

        self.zone_name = zone_name
        self.zone_id = zone_id
        self.zone_variable = zone_variable

        self._unique_id = '{} {}'.format(zone_variable, zone_id)
        self._data_id = data_id

        self._state = None
        self._state_attributes = None

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.zone_name, self.zone_variable)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._state_attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.zone_variable == "temperature":
            return self.hass.config.units.temperature_unit
        elif self.zone_variable == "humidity":
            return '%'
        elif self.zone_variable == "heating":
            return '%'

    @property
    def icon(self):
        """Icon for the sensor."""
        if self.zone_variable == "temperature":
            return 'mdi:thermometer'
        elif self.zone_variable == "humidity":
            return 'mdi:water-percent'

    def update(self):
        """Update method called when should_poll is true."""
        self._store.update()

        data = self._store.get_data(self._data_id)

        if data is None:
            _LOGGER.debug("Recieved no data for zone %s", self.zone_name)
            return

        unit = TEMP_CELSIUS

        # pylint: disable=R0912
        if self.zone_variable == 'temperature':
            if 'sensorDataPoints' in data:
                sensor_data = data['sensorDataPoints']
                temperature = float(
                    sensor_data['insideTemperature']['celsius'])

                self._state = self.hass.config.units.temperature(
                    temperature, unit)
                self._state_attributes = {
                    "time":
                        sensor_data['insideTemperature']['timestamp'],
                    "setting": 0  # setting is used in climate device
                }

                # temperature setting will not exist when device is off
                if 'temperature' in data['setting'] and \
                        data['setting']['temperature'] is not None:
                    temperature = float(
                        data['setting']['temperature']['celsius'])

                    self._state_attributes["setting"] = \
                        self.hass.config.units.temperature(
                            temperature, unit)

        elif self.zone_variable == 'humidity':
            if 'sensorDataPoints' in data:
                sensor_data = data['sensorDataPoints']
                self._state = float(
                    sensor_data['humidity']['percentage'])
                self._state_attributes = {
                    "time": sensor_data['humidity']['timestamp'],
                }

        elif self.zone_variable == 'power':
            if 'setting' in data:
                self._state = data['setting']['power']

        elif self.zone_variable == 'link':
            if 'link' in data:
                self._state = data['link']['state']

        elif self.zone_variable == 'heating':
            if 'activityDataPoints' in data:
                activity_data = data['activityDataPoints']
                self._state = float(
                    activity_data['heatingPower']['percentage'])
                self._state_attributes = {
                    "time": activity_data['heatingPower']['timestamp'],
                }

        elif self.zone_variable == 'tado bridge status':
            if 'connectionState' in data:
                self._state = data['connectionState']['value']

        elif self.zone_variable == 'tado mode':
            if 'tadoMode' in data:
                self._state = data['tadoMode']

        elif self.zone_variable == 'overlay':
            if 'overlay' in data and data['overlay'] is not None:
                self._state = True
                self._state_attributes = {
                    "termination": data['overlay']['termination']['type'],
                }
            else:
                self._state = False
                self._state_attributes = {}
