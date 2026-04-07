"""Sleep mode switch."""

from __future__ import annotations

from functools import cached_property
import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.helpers.typing import UndefinedType
from homeassistant.helpers.restore_state import RestoreEntity
from .auto_area import AutoArea
from .const import DOMAIN, NAME

_LOGGER: logging.Logger = logging.getLogger(__package__)


class SleepModeSwitch(SwitchEntity, RestoreEntity):
    """Set up a sleep mode switch."""

    _attr_should_poll = False

    def __init__(self) -> None:
        """Initialize sleep mode switch."""
        self._is_on: bool = False

    @cached_property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity."""
        return "Sleep Mode"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return "sleep_mode"

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self._is_on

    def turn_on(self, **kwargs) -> None:
        """Turn on switch."""

        self._is_on = True
        self.schedule_update_ha_state()
        self.hass.add_job(
            self.hass.bus.async_fire,
            "sleeping_switch_updated",
            {"is_on": self._is_on}
        )

    def turn_off(self, **kwargs):
        """Turn off switch."""

        self._is_on = False
        self.schedule_update_ha_state()
        self.hass.add_job(
            self.hass.bus.async_fire,
            "sleeping_switch_updated",
            {"is_on": self._is_on}
        ) 

    async def async_added_to_hass(self):
        """Restore previous state when entity is added."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._is_on = last_state.state == "on"