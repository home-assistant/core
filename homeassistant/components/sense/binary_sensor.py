"""Support for monitoring a Sense energy sensor device."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import SENSE_DATA

_LOGGER = logging.getLogger(__name__)

BIN_SENSOR_CLASS = 'power'
MDI_ICONS = {
    'ac': 'air-conditioner',
    'aquarium': 'fish',
    'car': 'car-electric',
    'computer': 'desktop-classic',
    'cup': 'coffee',
    'dehumidifier': 'water-off',
    'dishes': 'dishwasher',
    'drill': 'toolbox',
    'fan': 'fan',
    'freezer': 'fridge-top',
    'fridge': 'fridge-bottom',
    'game': 'gamepad-variant',
    'garage': 'garage',
    'grill': 'stove',
    'heat': 'fire',
    'heater': 'radiatior',
    'humidifier': 'water',
    'kettle': 'kettle',
    'leafblower': 'leaf',
    'lightbulb': 'lightbulb',
    'media_console': 'set-top-box',
    'modem': 'router-wireless',
    'outlet': 'power-socket-us',
    'papershredder': 'shredder',
    'printer': 'printer',
    'pump': 'water-pump',
    'settings': 'settings',
    'skillet': 'pot',
    'smartcamera': 'webcam',
    'socket': 'power-plug',
    'sound': 'speaker',
    'stove': 'stove',
    'trash': 'trash-can',
    'tv': 'television',
    'vacuum': 'robot-vacuum',
    'washer': 'washing-machine',
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Sense binary sensor."""
    if discovery_info is None:
        return
    data = hass.data[SENSE_DATA]

    sense_devices = await data.get_discovered_device_data()
    devices = [SenseDevice(data, device) for device in sense_devices
               if device['tags']['DeviceListAllowed'] == 'true']
    async_add_entities(devices)


def sense_to_mdi(sense_icon):
    """Convert sense icon to mdi icon."""
    return 'mdi:{}'.format(MDI_ICONS.get(sense_icon, 'power-plug'))


class SenseDevice(BinarySensorDevice):
    """Implementation of a Sense energy device binary sensor."""

    def __init__(self, data, device):
        """Initialize the Sense binary sensor."""
        self._name = device['name']
        self._id = device['id']
        self._icon = sense_to_mdi(device['icon'])
        self._data = data
        self._state = False

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the id of the binary sensor."""
        return self._id

    @property
    def icon(self):
        """Return the icon of the binary sensor."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return BIN_SENSOR_CLASS

    async def async_update(self):
        """Retrieve latest state."""
        from sense_energy.sense_api import SenseAPITimeoutException
        try:
            await self._data.update_realtime()
        except SenseAPITimeoutException:
            _LOGGER.error("Timeout retrieving data")
            return
        self._state = self._name in self._data.active_devices
