"""Support for the Fibaro devices."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pyfibaro.fibaro_device import DeviceModel

from homeassistant.const import ATTR_ARMED, ATTR_BATTERY_LEVEL
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


class FibaroEntity(Entity):
    """Representation of a Fibaro device entity."""

    _attr_should_poll = False

    def __init__(self, fibaro_device: DeviceModel) -> None:
        """Initialize the device."""
        self.fibaro_device = fibaro_device
        self.controller = fibaro_device.fibaro_controller
        self.ha_id = fibaro_device.ha_id
        self._attr_name = fibaro_device.friendly_name
        self._attr_unique_id = fibaro_device.unique_id_str

        self._attr_device_info = self.controller.get_device_info(fibaro_device)
        # propagate hidden attribute set in fibaro home center to HA
        if not fibaro_device.visible:
            self._attr_entity_registry_visible_default = False

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.controller.register(self.fibaro_device.fibaro_id, self._update_callback)

    def _update_callback(self) -> None:
        """Update the state."""
        self.schedule_update_ha_state(True)

    @property
    def level(self) -> int | None:
        """Get the level of Fibaro device."""
        if self.fibaro_device.value.has_value:
            return self.fibaro_device.value.int_value()
        return None

    @property
    def level2(self) -> int | None:
        """Get the tilt level of Fibaro device."""
        if self.fibaro_device.value_2.has_value:
            return self.fibaro_device.value_2.int_value()
        return None

    def dont_know_message(self, cmd: str) -> None:
        """Make a warning in case we don't know how to perform an action."""
        _LOGGER.warning(
            "Not sure how to %s: %s (available actions: %s)",
            cmd,
            str(self.ha_id),
            str(self.fibaro_device.actions),
        )

    def set_level(self, level: int) -> None:
        """Set the level of Fibaro device."""
        self.action("setValue", level)
        if self.fibaro_device.value.has_value:
            self.fibaro_device.properties["value"] = level
        if self.fibaro_device.has_brightness:
            self.fibaro_device.properties["brightness"] = level

    def set_level2(self, level: int) -> None:
        """Set the level2 of Fibaro device."""
        self.action("setValue2", level)
        if self.fibaro_device.value_2.has_value:
            self.fibaro_device.properties["value2"] = level

    def call_turn_on(self) -> None:
        """Turn on the Fibaro device."""
        self.action("turnOn")

    def call_turn_off(self) -> None:
        """Turn off the Fibaro device."""
        self.action("turnOff")

    def call_set_color(self, red: int, green: int, blue: int, white: int) -> None:
        """Set the color of Fibaro device."""
        red = int(max(0, min(255, red)))
        green = int(max(0, min(255, green)))
        blue = int(max(0, min(255, blue)))
        white = int(max(0, min(255, white)))
        color_str = f"{red},{green},{blue},{white}"
        self.fibaro_device.properties["color"] = color_str
        self.action("setColor", str(red), str(green), str(blue), str(white))

    def action(self, cmd: str, *args: Any) -> None:
        """Perform an action on the Fibaro HC."""
        if cmd in self.fibaro_device.actions:
            self.fibaro_device.execute_action(cmd, args)
            _LOGGER.debug("-> %s.%s%s called", str(self.ha_id), str(cmd), str(args))
        else:
            self.dont_know_message(cmd)

    @property
    def current_binary_state(self) -> bool:
        """Return the current binary state."""
        return self.fibaro_device.value.bool_value(False)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes of the device."""
        attr = {"fibaro_id": self.fibaro_device.fibaro_id}

        if self.fibaro_device.has_battery_level:
            attr[ATTR_BATTERY_LEVEL] = self.fibaro_device.battery_level
        if self.fibaro_device.has_armed:
            attr[ATTR_ARMED] = self.fibaro_device.armed

        return attr

    def update(self) -> None:
        """Update the available state of the entity."""
        if self.fibaro_device.has_dead:
            self._attr_available = not self.fibaro_device.dead
