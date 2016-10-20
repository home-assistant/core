"""Creates switches for the switches in the LiteJet lighting system."""
import voluptuous as vol
import logging
import homeassistant.components.litejet as litejet
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA

DEPENDENCIES = ['litejet']

ATTR_NUMBER = 'number'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the LiteJet switch platform."""
    litejet_ = litejet.CONNECTION

    devices = []
    for i in litejet_.button_switches():
        name = litejet_.get_switch_name(i)
        if not litejet.is_ignored(name):
            devices.append(LiteJetSwitch(hass, litejet_, i, name))
    add_devices(devices)


class LiteJetSwitch(SwitchDevice):
    """Represents a single LiteJet switch."""

    def __init__(self, hass, lj, i, name):
        """Initialize a LiteJet switch."""
        self._hass = hass
        self._lj = lj
        self._index = i
        self._state = False
        self._new_state = None
        self._name = name

        lj.on_switch_pressed(i, self._on_switch_pressed)
        lj.on_switch_released(i, self._on_switch_released)

        self.update()

    def _on_switch_pressed(self):
        _LOGGER.info("Updating pressed for %s", self._name)
        self._new_state = True
        self._hass.loop.create_task(self.async_update_ha_state(True))

    def _on_switch_released(self):
        _LOGGER.info("Updating released for %s", self._name)
        self._new_state = False
        self._hass.loop.create_task(self.async_update_ha_state(True))

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._state

    @property
    def should_poll(self):
        return False

    @property
    def device_state_attributes(self):
        return {
            ATTR_NUMBER: self._index
        }

    def turn_on(self, **kwargs):
        self._lj.press_switch(self._index)

    def turn_off(self, **kwargs):
        self._lj.release_switch(self._index)

    def update(self):
        if self._new_state is not None:
            self._state = self._new_state
