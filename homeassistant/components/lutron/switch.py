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
    entities: list[SwitchEntity] = []
    use_radiora_mode = config_entry.options.get(
        CONF_USE_RADIORA_MODE, config_entry.data.get(CONF_USE_RADIORA_MODE, False)
    )

    # Add Lutron Switches
    for device_name, device in entry_data.switches:
        entities.append(LutronSwitch(device_name, device, entry_data.controller))

    # Add Led as switches if radiora mode
    # Add the indicator LEDs for scenes (keypad buttons)
    if use_radiora_mode:
        for device_name, led in entry_data.leds:
            entities.append(
                LutronLedSwitch(device_name, led, entry_data.controller, config_entry)
            )

    async_add_entities(entities, True)


class LutronSwitch(LutronOutput, SwitchEntity):
    """Representation of a Lutron Switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._controller.output_set_level(self._lutron_device.id, 100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._controller.output_set_level(self._lutron_device.id, 0)

    async def _request_state(self):
        """Request the state of the switch."""
        await self._controller.output_get_level(self._lutron_device.id)

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
        device_name: str,
        lutron_device: Led,
        controller: LutronController,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the device."""
        super().__init__(device_name, lutron_device, controller)
        self._config_entry = config_entry
        self._attr_name = lutron_device.name

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._controller.device_turn_on(
            self._lutron_device.id, self._component_number
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._controller.device_turn_off(
            self._lutron_device.id, self._component_number
        )

    async def _request_state(self):
        await self._controller.device_get_state(
            self._lutron_device.id, self._component_number
        )

    def _update_callback(self, value: int):
        """Handle device LED state update."""
        self._attr_is_on = value == LIPLedState.ON
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {
            "keypad": self._lutron_device.keypad.name,
            "led": self._lutron_device.name,
        }
