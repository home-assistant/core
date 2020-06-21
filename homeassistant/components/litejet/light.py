"""Support for LiteJet lights."""
import logging

from homeassistant.components import litejet
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up lights for the LiteJet platform."""
    litejet_ = hass.data["litejet_system"]

    devices = []
    for i in litejet_.loads():
        name = litejet_.get_load_name(i)
        if not litejet.is_ignored(hass, name):
            devices.append(LiteJetLight(hass, litejet_, i, name))
    add_entities(devices, True)


class LiteJetLight(LightEntity):
    """Representation of a single LiteJet light."""

    def __init__(self, hass, lj, i, name):
        """Initialize a LiteJet light."""
        self._hass = hass
        self._lj = lj
        self._index = i
        self._brightness = 0
        self._name = name

        lj.on_load_activated(i, self._on_load_changed)
        lj.on_load_deactivated(i, self._on_load_changed)

    def _on_load_changed(self):
        """Handle state changes."""
        _LOGGER.debug("Updating due to notification for %s", self._name)
        self.schedule_update_ha_state(True)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def name(self):
        """Return the light's name."""
        return self._name

    @property
    def brightness(self):
        """Return the light's brightness."""
        return self._brightness

    @property
    def is_on(self):
        """Return if the light is on."""
        return self._brightness != 0

    @property
    def should_poll(self):
        """Return that lights do not require polling."""
        return False

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {ATTR_NUMBER: self._index}

    def turn_on(self, **kwargs):
        """Turn on the light."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] / 255 * 99)
            self._lj.activate_load_at(self._index, brightness, 0)
        else:
            self._lj.activate_load(self._index)

    def turn_off(self, **kwargs):
        """Turn off the light."""
        self._lj.deactivate_load(self._index)

    def update(self):
        """Retrieve the light's brightness from the LiteJet system."""
        self._brightness = self._lj.get_load_level(self._index) / 99 * 255
