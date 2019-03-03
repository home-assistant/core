"""Switch platform support for yeelight"""
import logging

from netdisco.const import ATTR_HOST

from homeassistant.const import CONF_DEVICES
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.yeelight import DATA_YEELIGHT, MODE_MOONLIGHT, \
    MODE_DAYLIGHT, DATA_UPDATED

DEPENDENCIES = ['yeelight']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Yeelight switches."""

    if not discovery_info:
        return

    device = hass.data[DATA_YEELIGHT][CONF_DEVICES][discovery_info[ATTR_HOST]]

    _LOGGER.debug("Adding power mode switch for %s", device.name)

    add_entities([YeelightPowerModeSwitch(device)])
    return True


class YeelightPowerModeSwitch(ToggleEntity):
    """Representation of a Yeelight power mode switch for night / moon light"""

    def __init__(self, device):
        self._device = device

    @callback
    def _schedule_immediate_update(self, ipaddr):
        if ipaddr == self._device.ipaddr:
            self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Handle entity which will be added."""

        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @property
    def should_poll(self):
        """No polling needed"""
        return False

    @property
    def is_on(self) -> bool:
        return self._device.is_nightlight_enabled

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} night light".format(self._device.name)

    @property
    def _bulb(self):
        return self._device.bulb

    @property
    def icon(self):
        return 'mdi:weather-night'

    def turn_on(self, **kwargs) -> None:
        self._device.set_mode(MODE_MOONLIGHT)

    def turn_off(self, **kwargs) -> None:
        self._device.set_mode(MODE_DAYLIGHT)
