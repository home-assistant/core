"""Switch platform support for yeelight"""
import logging

from netdisco.const import ATTR_HOST

from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.components.yeelight import DATA_YEELIGHT

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

    @property
    def is_on(self) -> bool:
        return self._bulb.last_properties.get('active_mode') == '1'

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
        import yeelight

        self._bulb.set_power_mode(yeelight.enums.PowerMode.MOONLIGHT)
        self._device.update()
        self.async_schedule_update_ha_state(True)

    def turn_off(self, **kwargs) -> None:
        import yeelight

        self._bulb.set_power_mode(yeelight.enums.PowerMode.NORMAL)
        self._device.update()
        self.async_schedule_update_ha_state(True)
