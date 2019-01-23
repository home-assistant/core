"""
Support for Fast.com internet speed testing sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fastdotcom/
"""
import logging

from homeassistant.components.fastdotcom import DOMAIN as FASTDOTCOM_DOMAIN, \
    DATA_UPDATED
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

DEPENDENCIES = ['fastdotcom']

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:speedometer'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fast.com sensor."""
    add_entities([SpeedtestSensor(hass.data[FASTDOTCOM_DOMAIN])])


class SpeedtestSensor(RestoreEntity):
    """Implementation of a FAst.com sensor."""

    def __init__(self, speedtest_data):
        """Initialize the sensor."""
        self._name = 'Fast.com Download'
        self.speedtest_client = speedtest_data
        self._state = None
        self._unit_of_measurement = 'Mbit/s'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data and update the states."""
        data = self.speedtest_client.data
        if data is None:
            return
        self._state = data['download']

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state

        async_dispatcher_connect(self.hass, DATA_UPDATED, self.update)

    @property
    def icon(self):
        """Return icon."""
        return ICON
