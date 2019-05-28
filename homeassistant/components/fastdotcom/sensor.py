"""Support for Fast.com internet speed testing sensor."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from . import DATA_UPDATED, DOMAIN as FASTDOTCOM_DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:speedometer'

UNIT_OF_MEASUREMENT = 'Mbit/s'


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Fast.com sensor."""
    async_add_entities([SpeedtestSensor(hass.data[FASTDOTCOM_DOMAIN])])


class SpeedtestSensor(RestoreEntity):
    """Implementation of a FAst.com sensor."""

    def __init__(self, speedtest_data):
        """Initialize the sensor."""
        self._name = 'Fast.com Download'
        self.speedtest_client = speedtest_data
        self._state = None

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
        return UNIT_OF_MEASUREMENT

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state

        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    def update(self):
        """Get the latest data and update the states."""
        data = self.speedtest_client.data
        if data is None:
            return
        self._state = data['download']

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)
