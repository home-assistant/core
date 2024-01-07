"""Support for Lutron switches."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pylutron import Button, Led, Lutron, Output

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, LutronData
from .entity import LutronDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    for area_name, keypad_name, scene, led in entry_data.scenes:
        if led is not None:
            entities.append(
                LutronLed(area_name, keypad_name, scene, led, entry_data.client)
            )
    async_add_entities(entities, True)


class LutronSwitch(LutronDevice, SwitchEntity):
    """Representation of a Lutron Switch."""

    _lutron_device: Output

    def __init__(
        self, area_name: str, lutron_device: Output, controller: Lutron
    ) -> None:
        """Initialize the switch."""
        self._prev_state = None
        super().__init__(area_name, lutron_device, controller)

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

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._lutron_device.last_level() > 0

    def update(self) -> None:
        """Call when forcing a refresh of the device."""
        if self._prev_state is None:
            self._prev_state = self._lutron_device.level > 0


class LutronLed(LutronDevice, SwitchEntity):
    """Representation of a Lutron Keypad LED."""

    _lutron_device: Led

    def __init__(
        self,
        area_name: str,
        keypad_name: str,
        scene_device: Button,
        led_device: Led,
        controller: Lutron,
    ) -> None:
        """Initialize the switch."""
        self._keypad_name = keypad_name
        self._scene_name = scene_device.name
        super().__init__(area_name, led_device, controller)

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
            "scene": self._scene_name,
            "led": self._lutron_device.name,
        }

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._lutron_device.last_state

    @property
    def name(self) -> str:
        """Return the name of the LED."""
        return f"{self._area_name} {self._keypad_name}: {self._scene_name} LED"

    def update(self) -> None:
        """Call when forcing a refresh of the device."""
        # The following property getter actually triggers an update in Lutron
        self._lutron_device.state  # pylint: disable=pointless-statement
