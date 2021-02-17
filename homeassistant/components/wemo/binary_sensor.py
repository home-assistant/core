"""Support for WeMo binary sensors."""
import asyncio
import logging

from pywemo.ouimeaux_device.api.service import ActionException

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoSubscriptionEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WeMo binary sensors."""

    async def _discovered_wemo(device):
        """Handle a discovered Wemo device."""
        async_add_entities([WemoBinarySensor(device)])

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.binary_sensor", _discovered_wemo)

    await asyncio.gather(
        *[
            _discovered_wemo(device)
            for device in hass.data[WEMO_DOMAIN]["pending"].pop("binary_sensor")
        ]
    )


class WemoBinarySensor(WemoSubscriptionEntity, BinarySensorEntity):
    """Representation a WeMo binary sensor."""

    def _update(self, force_update=True):
        """Update the sensor state."""
        try:
            self._state = self.wemo.get_state(force_update)

            if not self._available:
                _LOGGER.info("Reconnected to %s", self.name)
                self._available = True
        except ActionException as err:
            _LOGGER.warning("Could not update status for %s (%s)", self.name, err)
            self._available = False
            self.wemo.reconnect_with_device()
