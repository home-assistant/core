"""Platform to control a Salda Smarty XP/XV ventilation unit."""

import logging

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_UPDATE_SMARTY

_LOGGER = logging.getLogger(__name__)

SPEED_LIST = [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

SPEED_MAPPING = {1: SPEED_LOW, 2: SPEED_MEDIUM, 3: SPEED_HIGH}
SPEED_TO_MODE = {v: k for k, v in SPEED_MAPPING.items()}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Smarty Fan Platform."""
    smarty = hass.data[DOMAIN]["api"]
    name = hass.data[DOMAIN]["name"]

    async_add_entities([SmartyFan(name, smarty)], True)


class SmartyFan(FanEntity):
    """Representation of a Smarty Fan."""

    def __init__(self, name, smarty):
        """Initialize the entity."""
        self._name = name
        self._speed = SPEED_OFF
        self._state = None
        self._smarty = smarty

    @property
    def should_poll(self):
        """Do not poll."""
        return False

    @property
    def name(self):
        """Return the name of the fan."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:air-conditioner"

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed_list(self):
        """List of available fan modes."""
        return SPEED_LIST

    @property
    def is_on(self):
        """Return state of the fan."""
        return self._state

    @property
    def speed(self) -> str:
        """Return speed of the fan."""
        return self._speed

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        _LOGGER.debug("Set the fan speed to %s", speed)
        if speed == SPEED_OFF:
            self.turn_off()
        else:
            self._smarty.set_fan_speed(SPEED_TO_MODE.get(speed))
            self._speed = speed
            self._state = True

    def turn_on(self, speed=None, **kwargs):
        """Turn on the fan."""
        _LOGGER.debug("Turning on fan. Speed is %s", speed)
        if speed is None:
            if self._smarty.turn_on(SPEED_TO_MODE.get(self._speed)):
                self._state = True
                self._speed = SPEED_MEDIUM
        else:
            if self._smarty.set_fan_speed(SPEED_TO_MODE.get(speed)):
                self._speed = speed
                self._state = True

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn off the fan."""
        _LOGGER.debug("Turning off fan")
        if self._smarty.turn_off():
            self._state = False

        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Call to update fan."""
        async_dispatcher_connect(self.hass, SIGNAL_UPDATE_SMARTY, self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    def update(self):
        """Update state."""
        _LOGGER.debug("Updating state")
        result = self._smarty.fan_speed
        if result:
            self._speed = SPEED_MAPPING[result]
            _LOGGER.debug("Speed is %s, Mode is %s", self._speed, result)
            self._state = True
        else:
            self._state = False
