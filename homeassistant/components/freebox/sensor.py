"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
import logging

from homeassistant.helpers.entity import Entity

from . import DATA_FREEBOX_SENSOR

DEPENDENCIES = ['freebox']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the sensors."""
    datas = hass.data[DATA_FREEBOX_SENSOR]
    async_add_entities([FbxRXSensor(hass), FbxTXSensor(hass)], True)


class FbxRXSensor(Entity):
    """Update the Freebox RxSensor."""
    def __init__(self, hass):
        """Initialize the sensor."""
        self._state = None
        self._name = 'Freebox download speed'
        self._unit = 'KB/s'
        self._hass = hass
        self._data = None
        self._icon = 'mdi:download'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Define the unit."""
        return self._unit

    @property
    def icon(self):
        """Define the icon."""
        return self._icon

    async def async_update(self):
        """Get the value from fetched datas."""
        self._datas = self._hass.data[DATA_FREEBOX_SENSOR]
        if self._datas is not None:
            self._state = round(self._datas['rate_down'] / 1000, 2)


class FbxTXSensor(Entity):
    """Update the Freebox TxSensor."""
    def __init__(self, hass):
        """Initialize the sensor."""
        self._state = None
        self._name = 'Freebox upload speed'
        self._unit = 'KB/s'
        self._hass = hass
        self._datas = None
        self._icon = 'mdi:upload'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Define the unit."""
        return self._unit

    @property
    def icon(self):
        """Define the icon."""
        return self._icon

    async def async_update(self):
        """Get the value from fetched datas."""
        self._datas =  self._hass.data[DATA_FREEBOX_SENSOR]
        if self._datas is not None:
            self._state = round(self._datas['rate_up'] / 1000, 2)
