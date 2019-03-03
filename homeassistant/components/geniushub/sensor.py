"""
Supports Genius hub to provide room sensor and TRV information.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.geniushub/
"""
from homeassistant.components.geniushub import GENIUS_HUB
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_TEMPERATURE)
from homeassistant.helpers.entity import Entity

DOMAIN = 'geniushub'


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """Set up the Demo climate devices."""
    genius_hub = hass.data[GENIUS_HUB]
    await genius_hub.getjson('/zones')

    # Get sensors
    for sensor in genius_hub.getSensorList():
        async_add_entities([GeniusSensor(genius_hub, sensor)])

    # Get TRVs
    for trv in genius_hub.getTRVList():
        async_add_entities([GeniusTRV(genius_hub, trv)])


class GeniusSensor(Entity):
    """Representation of a Wall Sensor."""

    _genius_hub = None

    def __init__(self, genius_hub, sensor):
        """Initialize the Wall sensor."""
        GeniusSensor._genius_hub = genius_hub
        self._name = sensor['name'] + ' sensor ' + str(sensor['index'])
        self._device_id = sensor['iID']
        self._device_addr = sensor['addr']
        self._battery = sensor['Battery']
        self._temperature = sensor['TEMPERATURE']
        self._luminance = sensor['LUMINANCE']
        self._motion = sensor['Motion']

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._temperature

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return "genius_wall_sensor"

    @property
    def force_update(self):
        """Force update."""
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_BATTERY_LEVEL: self._battery,
            'luminance': self._luminance,
            'motion': self._motion,
            ATTR_TEMPERATURE: self._temperature
        }

    async def async_update(self):
        """Get the latest data."""
        device = GeniusSensor._genius_hub.getDevice(
            self._device_id, self._device_addr)
        data = GeniusSensor._genius_hub.getSensor(device)
        self._battery = data['Battery']
        self._temperature = data['TEMPERATURE']
        self._luminance = data['LUMINANCE']
        self._motion = data['Motion']


class GeniusTRV(Entity):
    """Representation of a TRV Sensor."""

    _genius_hub = None

    def __init__(self, genius_hub, trv):
        """Initialize the TRV sensor."""
        GeniusTRV._genius_hub = genius_hub
        self._name = trv['name'] + ' TRV ' + str(trv['index'])
        self._device_id = trv['iID']
        self._device_addr = trv['addr']
        self._battery = trv['Battery']
        self._temperature = trv['TEMPERATURE']

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._temperature

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return "genius_trv"

    @property
    def force_update(self):
        """Force update."""
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_BATTERY_LEVEL: self._battery,
            ATTR_TEMPERATURE: self._temperature
        }

    async def async_update(self):
        """Get the latest data."""
        device = GeniusTRV._genius_hub.getDevice(
            self._device_id, self._device_addr)
        data = GeniusTRV._genius_hub.getTRV(device)
        self._battery = data['Battery']
        self._temperature = data['TEMPERATURE']
