"""Support for pico and keypad buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDevice
from .const import DOMAIN as CASETA_DOMAIN
from .device_trigger import (
    LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP,
    _lutron_model_to_device_type,
)
from .models import LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lutron pico and keypad buttons."""
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data.bridge
    bridge_devices = bridge.get_devices()
    button_devices = bridge.get_buttons()

    for button_device_id in button_devices:
        # find and complete missing button names
        button_device = button_devices[button_device_id]
        ha_device = button_device
        if (
            "parent_device" in button_device
            and button_device["parent_device"] is not None
        ):
            ha_device = bridge_devices[button_device["parent_device"]]

        if "device_name" in button_device:
            continue

        # device name (button name) is missing, probably a caseta pico
        # try to get the name using the button number from the triggers
        # disable the button by default
        button_numbers = LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP.get(
            _lutron_model_to_device_type(ha_device["model"], ha_device["type"]),
            {},
        )
        button_device.update(
            {
                "device_name": button_numbers.get(
                    int(button_device["button_number"]),
                    f"button {button_device['button_number']}",
                ),
                "enabled_default": False,
            }
        )

    async_add_entities(
        LutronCasetaButton(button_devices[button_device_id], data)
        for button_device_id in button_devices
    )


class LutronCasetaButton(LutronCasetaDevice, ButtonEntity):
    """Representation of a Lutron pico and keypad button."""

    async def async_press(self) -> None:
        """Send a button press event."""
        await self._smartbridge.tap_button(self.device_id)

    @property
    def serial(self):
        """Buttons shouldn't have serial numbers, Return None."""
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"device_id": self.device_id}
