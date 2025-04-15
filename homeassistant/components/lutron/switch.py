"""Support for Lutron switches."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pylutron import Button, Keypad, Led, Lutron, Output

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, LutronData
from .entity import LutronDevice, LutronKeypad


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

    # Add Lutron Switches
    for area_name, device in entry_data.switches:
        entities.append(LutronSwitch(area_name, device, entry_data.client))

    # Add the indicator LEDs for scenes (keypad buttons)
    for area_name, keypad, scene, led in entry_data.scenes:
        if led is not None:
            entities.append(LutronLed(area_name, keypad, scene, led, entry_data.client))
    async_add_entities(entities, True)


class LutronSwitch(LutronDevice, SwitchEntity):
    """Representation of a Lutron Switch."""

    _lutron_device: Output
    _attr_name = None

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._lutron_device.level = 100

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._lutron_device.level = 0

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}

    def _request_state(self) -> None:
        """Request the state from the device."""
        _ = self._lutron_device.level

    def _update_attrs(self) -> None:
        """Update the state attributes."""
        self._attr_is_on = self._lutron_device.last_level() > 0


class LutronLed(LutronKeypad, SwitchEntity):
    """Representation of a Lutron Keypad LED."""

    _lutron_device: Led

    def __init__(
        self,
        area_name: str,
        keypad: Keypad,
        scene_device: Button,
        led_device: Led,
        controller: Lutron,
    ) -> None:
        """Initialize the switch."""
        super().__init__(area_name, led_device, controller, keypad)
        self._keypad_name = keypad.name
        self._attr_name = scene_device.name

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the LED on."""
        self._lutron_device.state = 1

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the LED off."""
        self._lutron_device.state = 0

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {
            "keypad": self._keypad_name,
            "scene": self._attr_name,
            "led": self._lutron_device.name,
        }

    def _request_state(self) -> None:
        """Request the state from the device."""
        _ = self._lutron_device.state

    def _update_attrs(self) -> None:
        """Update the state attributes."""
        self._attr_is_on = self._lutron_device.last_state
