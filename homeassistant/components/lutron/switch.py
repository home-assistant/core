"""Support for Lutron switches."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CONF_USE_RADIORA_MODE, DOMAIN, LutronData
from .aiolip import Led, LIPLedState, LutronController
from .entity import LutronKeypadComponent, LutronOutput


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron switch platform.

    Adds switches from the Main Repeater associated with the config_entry as
    switch entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]

    use_radiora_mode = config_entry.options.get(
        CONF_USE_RADIORA_MODE, config_entry.data.get(CONF_USE_RADIORA_MODE, False)
    )

    # Add Lutron Switches
    async_add_entities(
        (LutronSwitch(device, entry_data.controller) for device in entry_data.switches),
        True,
    )

    # Add Led as switches if radiora mode
    # Add the indicator LEDs for scenes (keypad buttons)
    if use_radiora_mode:
        async_add_entities(
            (
                LutronLedSwitch(device, entry_data.controller)
                for device in entry_data.leds
            ),
            True,
        )


class LutronSwitch(LutronOutput, SwitchEntity):
    """Representation of a Lutron Switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._execute_device_command(self._lutron_device.set_level, 100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._execute_device_command(self._lutron_device.set_level, 0)

    async def _request_state(self):
        """Request the state of the switch."""
        await self._execute_device_command(self._lutron_device.get_level)

    def _update_callback(self, value: float):
        """Set switch state."""
        self._attr_is_on = value > 0
        self.async_write_ha_state()


class LutronLedSwitch(LutronKeypadComponent, SwitchEntity):
    """Representation of a Lutron Led as a switch."""

    _lutron_device: Led
    _attr_is_on: bool | None = None

    def __init__(
        self,
        lutron_device: Led,
        controller: LutronController,
    ) -> None:
        """Initialize the device."""
        super().__init__(lutron_device, controller)
        self._attr_name = self.name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LED on."""
        await self._execute_device_command(self._lutron_device.turn_on)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LED off."""
        await self._execute_device_command(self._lutron_device.turn_off)

    async def _request_state(self):
        """Request the state of the LED."""
        await self._execute_device_command(self._lutron_device.get_state)

    def _update_callback(self, value: int):
        """Set LED state."""
        self._attr_is_on = value == LIPLedState.ON
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {
            "keypad": self.keypad_name,
            "led": self.name,
        }
