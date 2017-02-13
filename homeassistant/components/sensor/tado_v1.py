"""tado component to create some sensors for each zone."""

import logging
from datetime import timedelta

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

#  DOMAIN = 'tado_v1'

_LOGGER = logging.getLogger(__name__)
SENSOR_TYPES = ['temperature', 'humidity', 'power',
                'link', 'heating', 'tado mode', 'overlay']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    #  pylint: disable=W0613

    #  get the PyTado object from the hub component
    tado = hass.data['Mytado']

    try:
        zones = tado.getZones()
    except RuntimeError:
        _LOGGER.error("Unable to get zone info from mytado")
        return False

    tado_data = TadoData(tado, MIN_TIME_BETWEEN_SCANS)

    sensor_items = []
    for zone in zones:
        if zone['type'] == 'HEATING':
            for variable in SENSOR_TYPES:
                sensor_items.append(tado_data.create_zone_sensor(
                    zone, zone['name'], zone['id'], variable))

    me_data = tado.getMe()
    sensor_items.append(tado_data.create_device_sensor(
        me_data, me_data['homes'][0]['name'],
        me_data['homes'][0]['id'],
        "tado bridge status"))

    tado_data.update()

    if len(sensor_items) > 0:
        add_devices(sensor_items)
        return True
    else:
        return False


class TadoSensor(Entity):
    """Representation of a tado Sensor."""

    def __init__(self, tado_data, zone_name, zone_id, zone_variable, data_id):
        """Initialization of TadoSensor class."""
        self._tado_data = tado_data
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
            return TEMP_CELSIUS
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
        self._tado_data.update()

        self.push_update(self._tado_data.get_data(self._data_id), True)

    def push_update(self, data, update_ha):
        """Push the update to the current object."""
        # pylint: disable=R0912
        if self.zone_variable == 'temperature':
            if 'sensorDataPoints' in data:
                sensor_data = data['sensorDataPoints']
                self._state = float(
                    sensor_data['insideTemperature']['celsius'])
                self._state_attributes = {
                    "time":
                        sensor_data['insideTemperature']['timestamp'],
                    "setting": 0  # setting is used in climate device
                }

                # temperature setting will not exist when device is off
                if 'temperature' in data['setting'] and \
                        data['setting']['temperature'] is not None:
                    self._state_attributes["setting"] = float(
                        data['setting']['temperature']['celsius'])

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
                # pylint: disable=R0204
                self._state = True
                self._state_attributes = {
                    "termination": data['overlay']['termination']['type'],
                }
            else:
                self._state = False
                self._state_attributes = {}

        if update_ha:
            self.schedule_update_ha_state()


class TadoData(object):
    """Tado data object to control the tado functionality."""

    def __init__(self, tado, interval):
        """Initialization of TadoData class."""
        self._tado = tado

        self.sensors = {}
        self.data = {}

        # Apply throttling to methods using configured interval
        self.update = Throttle(interval)(self._update)

    def create_zone_sensor(self, zone, name, zone_id, variable):
        """Create a zone sensor."""
        data_id = 'zone {} {}'.format(name, zone_id)

        self.sensors[data_id] = {
            "zone": zone,
            "name": name,
            "id": zone_id,
            "data_id": data_id
        }
        self.data[data_id] = None

        return TadoSensor(self, name, zone_id, variable, data_id)

    def create_device_sensor(self, device, name, device_id, variable):
        """Create a device sensor."""
        data_id = 'device {} {}'.format(name, device_id)

        self.sensors[data_id] = {
            "device": device,
            "name": name,
            "id": device_id,
            "data_id": data_id
        }
        self.data[data_id] = None

        return TadoSensor(self, name, device_id, variable, data_id)

    def get_data(self, data_id):
        """Get the cached data."""
        data = {"error": "no data"}

        if data_id in self.data:
            data = self.data[data_id]

        return data

    def _update(self):
        """Update the internal data-array from mytado.com."""
        for data_id, sensor in self.sensors.items():
            data = None

            try:
                if "zone" in sensor:
                    _LOGGER.info("querying mytado.com for zone %s %s",
                                 sensor["id"], sensor["name"])
                    data = self._tado.getState(sensor["id"])
                if "device" in sensor:
                    _LOGGER.info("querying mytado.com for device %s %s",
                                 sensor["id"], sensor["name"])
                    data = self._tado.getDevices()[0]

            except RuntimeError:
                _LOGGER.error("Unable to connect to myTado. %s %s",
                              sensor["id"], sensor["id"])

            self.data[data_id] = data
