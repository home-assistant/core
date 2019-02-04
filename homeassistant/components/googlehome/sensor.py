"""
Support for Google Home alarm sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.googlehome/
"""
import logging
from datetime import timedelta

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.googlehome import (
    CLIENT, DOMAIN as GOOGLEHOME_DOMAIN, NAME)
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.entity import Entity, async_generate_entity_id
import homeassistant.util.dt as dt_util


DEPENDENCIES = ['googlehome']

SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:alarm'

SENSOR_TYPES = {
    'timer': "Timer",
    'alarm': "Alarm",
}


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """Set up the googlehome sensor platform."""
    if discovery_info is None:
        _LOGGER.warning(
            "To use this you need to configure the 'googlehome' component")

    devices = []
    for condition in SENSOR_TYPES:
        device = GoogleHomeAlarm(hass.data[CLIENT], condition,
                                 discovery_info)
        devices.append(device)

    async_add_entities(devices, True)


class GoogleHomeAlarm(Entity):
    """Representation of a GoogleHomeAlarm."""

    def __init__(self, client, condition, config):
        """Initialize the GoogleHomeAlarm sensor."""
        self._host = config['host']
        self._client = client
        self._condition = condition
        self._name = None
        self._state = None
        self._available = True

    async def async_added_to_hass(self):
        """Subscribe GoogleHome events."""
        await self._client.update_info(self._host)
        data = self.hass.data[GOOGLEHOME_DOMAIN][self._host]
        info = data.get('info', {})
        if info is None:
            return
        self._name = "{} {}".format(info.get('name', NAME),
                                    SENSOR_TYPES[self._condition])
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self._name, hass=self.hass)

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
