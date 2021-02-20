"""Platform to control a Salda Smarty XP/XV ventilation unit."""

import logging
import math
from typing import Optional

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import DOMAIN, SIGNAL_UPDATE_SMARTY

_LOGGER = logging.getLogger(__name__)

DEFAULT_ON_PERCENTAGE = 66
SPEED_RANGE = (1, 3)  # off is not included


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
        self._smarty_fan_speed = 0
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
    def is_on(self):
        """Return state of the fan."""
        return bool(self._smarty_fan_speed)

    @property
    def speed_count(self) -> Optional[int]:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def percentage(self) -> str:
        """Return speed percentage of the fan."""
        if self._smarty_fan_speed == 0:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, self._smarty_fan_speed)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Set the fan percentage to %s", percentage)
        if percentage == 0:
            self.turn_off()
            return

        fan_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        if not self._smarty.set_fan_speed(fan_speed):
            raise HomeAssistantError(
                f"Failed to set the fan speed percentage to {percentage}"
            )

        self._smarty_fan_speed = fan_speed
        self.schedule_update_ha_state()

    def turn_on(self, speed=None, percentage=None, preset_mode=None, **kwargs):
        """Turn on the fan."""
        _LOGGER.debug("Turning on fan. Speed is %s", speed)
        self.set_percentage(percentage or DEFAULT_ON_PERCENTAGE)

    def turn_off(self, **kwargs):
        """Turn off the fan."""
        _LOGGER.debug("Turning off fan")
        if not self._smarty.turn_off():
            raise HomeAssistantError("Failed to turn off the fan")

        self._smarty_fan_speed = 0
        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Call to update fan."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_SMARTY, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        _LOGGER.debug("Updating state")
        self._smarty_fan_speed = self._smarty.fan_speed
        self.async_write_ha_state()
