"""Support for JLR InControl sensors."""
import logging

from homeassistant.components.jlrincontrol import (
    SIGNAL_STATE_UPDATED
)

from homeassistant.components.jlrincontrol import JLREntity, RESOURCES
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the JLR sensors."""
    if discovery_info is None:
        return
    add_entities([JLRSensor(hass, *discovery_info)])


class JLRSensor(JLREntity):
    """Representation of a JLR Sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        _LOGGER.info("Updating ==========================================")
        val = self.get_updated_info()
        if val is None:
            return val
        if val:
            val = val[self._attribute]
        else:
            return None

        if self._attribute in ['last_connected', 'service_inspection',
                               'oil_inspection']:
            return str(val)
        if self._attribute in ['ODOMETER_METER']:
            return float(int(val) / 1000)

        return int(float(val))

    def update(self):
        _LOGGER.info("Updating here xxxxxxxxxxxxx")

    async def async_added_to_hass(self):
        _LOGGER.info("CONNECTING TO DISPATCHER ==============================================")
        async_dispatcher_connect(self.hass, SIGNAL_STATE_UPDATED, self._schedule_immediate_update)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return RESOURCES[self._attribute][3]

    @property
    def icon(self):
        """Return the icon."""
        return RESOURCES[self._attribute][2]

    @callback
    def _schedule_immediate_update(self):
        _LOGGER.info("IN CALLBACK HERE ==========XXXXXXXXXXXXXXXXXX===================")
        self.async_schedule_update_ha_state(True)
