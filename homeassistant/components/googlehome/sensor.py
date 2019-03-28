"""Support for Google Home alarm sensor."""
from datetime import timedelta
import logging

from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

from . import CLIENT, DOMAIN as GOOGLEHOME_DOMAIN, NAME

DEPENDENCIES = ['googlehome']

SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:alarm'

SENSOR_TYPES = {
    'timer': 'Timer',
    'alarm': 'Alarm',
}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the googlehome sensor platform."""
    if discovery_info is None:
        _LOGGER.warning(
            "To use this you need to configure the 'googlehome' component")
        return

    await hass.data[CLIENT].update_info(discovery_info['host'])
    data = hass.data[GOOGLEHOME_DOMAIN][discovery_info['host']]
    info = data.get('info', {})

    devices = []
    for condition in SENSOR_TYPES:
        device = GoogleHomeAlarm(hass.data[CLIENT], condition,
                                 discovery_info, info.get('name', NAME))
        devices.append(device)

    async_add_entities(devices, True)


class GoogleHomeAlarm(Entity):
    """Representation of a GoogleHomeAlarm."""

    def __init__(self, client, condition, config, name):
        """Initialize the GoogleHomeAlarm sensor."""
        self._host = config['host']
        self._client = client
        self._condition = condition
        self._name = None
        self._state = None
        self._available = True
        self._name = "{} {}".format(name, SENSOR_TYPES[self._condition])

    async def async_update(self):
        """Update the data."""
        await self._client.update_alarms(self._host)
        data = self.hass.data[GOOGLEHOME_DOMAIN][self._host]

        alarms = data.get('alarms')[self._condition]
        if not alarms:
            self._available = False
            return
        self._available = True
        time_date = dt_util.utc_from_timestamp(min(element['fire_time']
                                                   for element in alarms)
                                               / 1000)
        self._state = time_date.isoformat()

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def available(self):
        """Return the availability state."""
        return self._available

    @property
    def icon(self):
        """Return the icon."""
        return ICON
