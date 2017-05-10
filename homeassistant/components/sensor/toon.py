"""
Toon van Eneco Utility Gages.
This provides a component for the rebranded Quby thermostat as provided by
Eneco.
"""
import logging

from homeassistant.helpers.entity import Entity
import homeassistant.components.toon as toon_main
import datetime as datetime

_LOGGER = logging.getLogger(__name__)

STATE_ATTR_DEVICE_TYPE = "device_type"
STATE_ATTR_LAST_CONNECTED_CHANGE = "last_connected_change"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup sensors."""
    _toon_main = hass.data[toon_main.TOON_HANDLE]

    add_devices([
        ToonSensor(hass, 'Power_current', 'Watt'),
        ToonSensor(hass, 'Power_today', 'kWh')
    ])

    if _toon_main.gas:
        add_devices([
            ToonSensor(hass, 'Gas_current', 'CM3'),
            ToonSensor(hass, 'Gas_today', 'M3')
        ])
    
    for plug in _toon_main.toon.smartplugs:
        add_devices([
            FibaroSensor(hass,
                         '{}_current_power'.format(plug.name),
                         plug.name,
                         'Watt'),
            FibaroSensor(hass,
                         '{}_today_energy'.format(plug.name),
                         plug.name,
                         'kWh')])

    if _toon_main.toon.solar.produced or _toon_main.solar:
        add_devices([
            SolarSensor(hass, 'Solar_maximum', 'kWh'),
            SolarSensor(hass, 'Solar_produced', 'kWh'),
            SolarSensor(hass, 'Solar_value', 'Watt'),
            SolarSensor(hass, 'Solar_average_produced', 'kWh'),
            SolarSensor(hass, 'Solar_meter_reading_low_produced', 'kWh'),
            SolarSensor(hass, 'Solar_meter_reading_produced', 'kWh'),
            SolarSensor(hass, 'Solar_daily_cost_produced', 'Euro')
        ])

    for smokedetector in _toon_main.toon.smokedetectors:
        add_devices([
            FibaroSmokeDetector(hass,
                                '{}_smoke_detector'.format(smokedetector.name),
                                smokedetector.device_uuid,
                                '%')])


class ToonSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, hass, name, unit_of_measurement):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self.thermos = hass.data[toon_main.TOON_HANDLE]

    @property
    def should_poll(self):
        """Polling required"""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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
    """Representation of a sensor."""

    def __init__(self, hass, name, plug_name, unit_of_measurement):
        """Initialize the sensor."""
        self._name = name
        self._plug_name = plug_name
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self.toon = hass.data[toon_main.TOON_HANDLE]

    @property
    def should_poll(self):
        """Polling required"""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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
    """Representation of a sensor."""

    def __init__(self, hass, name, unit_of_measurement):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self.toon = hass.data[toon_main.TOON_HANDLE]

    @property
    def should_poll(self):
        """Polling required"""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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
    """Representation of a smoke detector."""

    def __init__(self, hass, name, uid, unit_of_measurement):
        """Initialize the sensor."""
        self._name = name
        self._uid = uid
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self.toon = hass.data[toon_main.TOON_HANDLE]

    @property
    def should_poll(self):
        """Polling required"""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state_attributes(self):
        """Return the state attributes of the smoke detectors."""
        value = datetime.datetime.fromtimestamp(
                    int(self.toon.get_data('last_connected_change', self.name))
                ).strftime('%Y-%m-%d %H:%M:%S')

        return {
            STATE_ATTR_DEVICE_TYPE: self.toon.get_data('device_type', self.name),
            STATE_ATTR_LAST_CONNECTED_CHANGE: value   
        }

    @property
    def state(self):
        """Return the state of the sensor."""
        value = '_'.join(self.name.lower().split('_')[1:])
        return self.toon.get_data(value, self.name)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the sensor."""
        self.toon.update()