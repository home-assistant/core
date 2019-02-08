"""
Component for the rebranded Quby thermostat as provided by Eneco.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.toon/
"""
import logging
import datetime

from homeassistant.helpers.entity import Entity
import homeassistant.components.toon as toon_main

_LOGGER = logging.getLogger(__name__)

STATE_ATTR_DEVICE_TYPE = 'device_type'
STATE_ATTR_LAST_CONNECTED_CHANGE = 'last_connected_change'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Toon sensors."""
    _toon_main = hass.data[toon_main.TOON_HANDLE]

    sensor_items = []
    sensor_items.extend([
        ToonSensor(hass, 'Power_current', 'power-plug', 'Watt'),
        ToonSensor(hass, 'Power_today', 'power-plug', 'kWh'),
    ])

    if _toon_main.gas:
        sensor_items.extend([
            ToonSensor(hass, 'Gas_current', 'gas-cylinder', 'CM3'),
            ToonSensor(hass, 'Gas_today', 'gas-cylinder', 'M3'),
        ])

    for plug in _toon_main.toon.smartplugs:
        sensor_items.extend([
            FibaroSensor(hass, '{}_current_power'.format(plug.name),
                         plug.name, 'power-socket-eu', 'Watt'),
            FibaroSensor(hass, '{}_today_energy'.format(plug.name),
                         plug.name, 'power-socket-eu', 'kWh'),
        ])

    if _toon_main.toon.solar.produced or _toon_main.solar:
        sensor_items.extend([
            SolarSensor(hass, 'Solar_maximum', 'kWh'),
            SolarSensor(hass, 'Solar_produced', 'kWh'),
            SolarSensor(hass, 'Solar_value', 'Watt'),
            SolarSensor(hass, 'Solar_average_produced', 'kWh'),
            SolarSensor(hass, 'Solar_meter_reading_low_produced', 'kWh'),
            SolarSensor(hass, 'Solar_meter_reading_produced', 'kWh'),
            SolarSensor(hass, 'Solar_daily_cost_produced', 'Euro'),
        ])

    for smokedetector in _toon_main.toon.smokedetectors:
        sensor_items.append(
            FibaroSmokeDetector(
                hass, '{}_smoke_detector'.format(smokedetector.name),
                smokedetector.device_uuid, 'alarm-bell', '%')
        )

    add_entities(sensor_items)


class ToonSensor(Entity):
    """Representation of a Toon sensor."""

    def __init__(self, hass, name, icon, unit_of_measurement):
        """Initialize the Toon sensor."""
        self._name = name
        self._state = None
        self._icon = 'mdi:{}'.format(icon)
        self._unit_of_measurement = unit_of_measurement
        self.thermos = hass.data[toon_main.TOON_HANDLE]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the mdi icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.thermos.get_data(self.name.lower())

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the sensor."""
        self.thermos.update()


class FibaroSensor(Entity):
    """Representation of a Fibaro sensor."""

    def __init__(self, hass, name, plug_name, icon, unit_of_measurement):
        """Initialize the Fibaro sensor."""
        self._name = name
        self._plug_name = plug_name
        self._state = None
        self._icon = 'mdi:{}'.format(icon)
        self._unit_of_measurement = unit_of_measurement
        self.toon = hass.data[toon_main.TOON_HANDLE]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the mdi icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        value = '_'.join(self.name.lower().split('_')[1:])
        return self.toon.get_data(value, self._plug_name)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the sensor."""
        self.toon.update()


class SolarSensor(Entity):
    """Representation of a Solar sensor."""

    def __init__(self, hass, name, unit_of_measurement):
        """Initialize the Solar sensor."""
        self._name = name
        self._state = None
        self._icon = 'mdi:weather-sunny'
        self._unit_of_measurement = unit_of_measurement
        self.toon = hass.data[toon_main.TOON_HANDLE]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the mdi icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.toon.get_data(self.name.lower())

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the sensor."""
        self.toon.update()


class FibaroSmokeDetector(Entity):
    """Representation of a Fibaro smoke detector."""

    def __init__(self, hass, name, uid, icon, unit_of_measurement):
        """Initialize the Fibaro smoke sensor."""
        self._name = name
        self._uid = uid
        self._state = None
        self._icon = 'mdi:{}'.format(icon)
        self._unit_of_measurement = unit_of_measurement
        self.toon = hass.data[toon_main.TOON_HANDLE]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the mdi icon of the sensor."""
        return self._icon

    @property
    def state_attributes(self):
        """Return the state attributes of the smoke detectors."""
        value = datetime.datetime.fromtimestamp(
            int(self.toon.get_data('last_connected_change', self.name))
        ).strftime('%Y-%m-%d %H:%M:%S')

        return {
            STATE_ATTR_DEVICE_TYPE:
                self.toon.get_data('device_type', self.name),
            STATE_ATTR_LAST_CONNECTED_CHANGE: value,
        }

    @property
    def state(self):
        """Return the state of the sensor."""
        value = self.name.lower().split('_', 1)[1]
        return self.toon.get_data(value, self.name)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the sensor."""
        self.toon.update()
