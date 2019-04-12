"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
import logging

from homeassistant.helpers.entity import Entity

from . import DATA_FREEBOX

DEPENDENCIES = ['freebox']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the sensors."""
    fbx = hass.data[DATA_FREEBOX]
    async_add_entities([FbxRXSensor(fbx), FbxTXSensor(fbx)], True)


class FbxSensor(Entity):
    """Representation of a freebox sensor."""

    _name = 'generic'

    def __init__(self, fbx):
        """Initialize the sensor."""
        self._fbx = fbx
        self._state = None
        self._datas = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch status from freebox."""
        self._datas = await self._fbx.connection.get_status()


class FbxRXSensor(FbxSensor):
    """Update the Freebox RxSensor."""

    _name = 'Freebox download speed'
    _unit = 'KB/s'

    @property
    def unit_of_measurement(self):
        """Define the unit."""
        return self._unit

    async def async_update(self):
        """Get the value from fetched datas."""
        await super().async_update()
        if self._datas is not None:
            self._state = round(self._datas['rate_down'] / 1000, 2)


class FbxTXSensor(FbxSensor):
    """Update the Freebox TxSensor."""

    _name = 'Freebox upload speed'
    _unit = 'KB/s'

    @property
    def unit_of_measurement(self):
        """Define the unit."""
        return self._unit

    async def async_update(self):
        """Get the value from fetched datas."""
        await super().async_update()
        if self._datas is not None:
            self._state = round(self._datas['rate_up'] / 1000, 2)
