"""Support for pico and keypad buttons."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device_trigger import LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP
from .entity import LutronCasetaEntity
from .models import LutronCasetaConfigEntry, LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronCasetaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lutron pico and keypad buttons."""
    data = config_entry.runtime_data
    bridge = data.bridge
    button_devices = bridge.get_buttons()
    all_devices = data.bridge.get_devices()
    keypads = data.keypad_data.keypads
    entities: list[LutronCasetaButton] = []

    for device in button_devices.values():
        parent_keypad = keypads[device["parent_device"]]
        parent_device_info = parent_keypad["device_info"]

        enabled_default = True
        if not (device_name := device.get("device_name")):
            # device name (button name) is missing, probably a caseta pico
            # try to get the name using the button number from the triggers
            # disable the button by default
            enabled_default = False
            keypad_device = all_devices[device["parent_device"]]
            button_numbers = LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP.get(
                keypad_device["type"],
                {},
            )
            device_name = (
                button_numbers.get(
                    int(device["button_number"]),
                    f"button {device['button_number']}",
                )
                .replace("_", " ")
                .title()
            )

        # Append the child device name to the end of the parent keypad
        # name to create the entity name
        full_name = f'{parent_device_info.get("name")} {device_name}'
        # Set the device_info to the same as the Parent Keypad
        # The entities will be nested inside the keypad device
        entities.append(
            LutronCasetaButton(
                device, data, full_name, enabled_default, parent_device_info
            ),
        )

    async_add_entities(entities)


class LutronCasetaButton(LutronCasetaEntity, ButtonEntity):
    """Representation of a Lutron pico and keypad button."""

    def __init__(
        self,
        device: dict[str, Any],
        data: LutronCasetaData,
        full_name: str,
        enabled_default: bool,
        device_info: DeviceInfo,
    ) -> None:
        """Init a button entity."""
        super().__init__(device, data)
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_name = full_name
        self._attr_device_info = device_info

    async def async_press(self) -> None:
        """Send a button press event."""
        await self._smartbridge.tap_button(self.device_id)

    @property
    def serial(self):
        """Buttons shouldn't have serial numbers, Return None."""
        return None
