"""Support for Balboa Spa switches."""
import logging

from homeassistant.components.switch import DEVICE_CLASS_SWITCH, SwitchDevice
from homeassistant.const import CONF_NAME

from . import BalboaEntity
from .const import DOMAIN as BALBOA_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up of the spa is done through async_setup_entry."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the spa switch devices."""
    spa = hass.data[BALBOA_DOMAIN][entry.entry_id]
    name = entry.data[CONF_NAME]
    devs = []

    lights = spa.get_light_list()
    if lights[0]:
        devs.append(BalboaSpaSwitch(hass, spa, f"{name}-light1", "light1"))
    if lights[1]:
        devs.append(BalboaSpaSwitch(hass, spa, f"{name}-light2", "light2"))
    auxs = spa.get_aux_list()
    if auxs[0]:
        devs.append(BalboaSpaSwitch(hass, spa, f"{name}-aux1", "aux1"))
    if auxs[1]:
        devs.append(BalboaSpaSwitch(hass, spa, f"{name}-aux2", "aux2"))
    if spa.have_mister():
        devs.append(BalboaSpaSwitch(hass, spa, f"{name}-mister", "mister"))

    async_add_entities(devs, True)


class BalboaSpaSwitch(BalboaEntity, SwitchDevice):
    """Representation of a Balboa Spa switch device."""

    def __init__(self, hass, client, name, switch_key):
        """Initialize the switch."""
        super().__init__(hass, client, name)
        self.switch_key = switch_key
        self.getdata = {
            "light1": self._client.get_light,
            "light2": self._client.get_light,
            "aux1": self._client.get_aux,
            "aux2": self._client.get_aux,
        }
        self.switch_change = {
            "light1": self._client.change_light,
            "light2": self._client.change_light,
            "aux1": self._client.change_aux,
            "aux2": self._client.change_aux,
        }

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        if "mister" in self.switch_key:
            return self._client.get_mister()
        num = int(self.switch_key[-1]) - 1
        return self.getdata[self.switch_key](num)

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SWITCH

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if "mister" in self.switch_key:
            return "mdi:weather-fog"
        if "light" in self.switch_key:
            return "mdi:lightbulb"
        return "mdi:flash"

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        if "mister" in self.switch_key:
            return self._client.change_mister(self._client.OFF)
        num = int(self.switch_key[-1]) - 1
        await self.switch_change[self.switch_key](num, self._client.OFF)

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        if "mister" in self.switch_key:
            return self._client.change_mister(self._client.ON)
        num = int(self.switch_key[-1]) - 1
        await self.switch_change[self.switch_key](num, self._client.ON)
