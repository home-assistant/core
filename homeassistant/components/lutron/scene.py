"""Support for Lutron scenes."""
import logging
from typing import Any

from homeassistant.components.scene import Scene

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up scenes for a Lutron Deployment."""
    async_add_entities(
        (
            LutronScene(
                area,
                keypad,
                device,
                led,
                hass.data[DOMAIN][entry.entry_id][LUTRON_CONTROLLER],
            )
            for (area, keypad, device, led) in hass.data[DOMAIN][entry.entry_id][
                LUTRON_DEVICES
            ]["scene"]
        ),
        True,
    )


class LutronScene(LutronDevice, Scene):
    """Representation of a Lutron Scene."""

    def __init__(self, area, keypad, lutron_device, lutron_led, controller):
        """Initialize the scene/button."""
        self._keypad = keypad
        self._led = lutron_led
        super().__init__(area, lutron_device, controller)
        self._keypad_unique_id = f"{self._controller.guid}_{self._keypad.uuid}"

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self._lutron_device.press()

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._area.name} {self._keypad.name}: {self._lutron_device.name}"

    @property
    def device_info(self):
        """Return key device information."""
        device_info = {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._keypad_unique_id)
            },
            "name": f"{self._area.name} {self._keypad.name}",
            "manufacturer": "Lutron",
            "model": self._keypad.type,
            # "sw_version": self.light.swversion,
            "via_device": (DOMAIN, self._lutron_device._lutron.guid),
            "area_id": self._area.id,
        }
        if self._area.id:
            device_info["area_id"] = self._area.id
        return device_info
