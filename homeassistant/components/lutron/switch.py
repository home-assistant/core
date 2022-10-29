"""Support for Lutron switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Lutron switches."""
    devs = []

    # Add Lutron Switches
    for (area_name, device) in hass.data[LUTRON_DEVICES]["switch"]:
        dev = LutronSwitch(area_name, device, hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    # Add the indicator LEDs for scenes (keypad buttons)
    for scene_data in hass.data[LUTRON_DEVICES]["scene"]:
        (area_name, keypad_name, scene, led) = scene_data
        if led is not None:
            led = LutronLed(
                area_name, keypad_name, scene, led, hass.data[LUTRON_CONTROLLER]
            )
            devs.append(led)

    add_entities(devs, True)


class LutronSwitch(LutronDevice, SwitchEntity):
    """Representation of a Lutron Switch."""

    def __init__(self, area_name, lutron_device, controller):
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
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._lutron_device.last_level() > 0

    def update(self) -> None:
        """Call when forcing a refresh of the device."""
        if self._prev_state is None:
            self._prev_state = self._lutron_device.level > 0


class LutronLed(LutronDevice, SwitchEntity):
    """Representation of a Lutron Keypad LED."""

    def __init__(self, area_name, keypad_name, scene_device, led_device, controller):
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
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "keypad": self._keypad_name,
            "scene": self._scene_name,
            "led": self._lutron_device.name,
        }

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._lutron_device.last_state

    @property
    def name(self) -> str:
        """Return the name of the LED."""
        return f"{self._area_name} {self._keypad_name}: {self._scene_name} LED"

    def update(self) -> None:
        """Call when forcing a refresh of the device."""
        if self._lutron_device.last_state is not None:
            return

        # The following property getter actually triggers an update in Lutron
        self._lutron_device.state  # pylint: disable=pointless-statement
