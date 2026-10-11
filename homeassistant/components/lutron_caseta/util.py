"""Support for Lutron Caseta."""

from collections.abc import Iterator
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import UNASSIGNED_AREA
from .device_trigger import LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP
from .models import LutronCasetaData


def serial_to_unique_id(serial: int) -> str:
    """Convert a lutron serial number to a unique id."""
    return hex(serial)[2:].zfill(8)


def area_name_from_id(areas: dict[str, dict], area_id: str | None) -> str:
    """Return the full area name including parent(s)."""
    if area_id is None:
        return UNASSIGNED_AREA
    return _construct_area_name_from_id(areas, area_id, [])


def _construct_area_name_from_id(
    areas: dict[str, dict], area_id: str, labels: list[str]
) -> str:
    """Recursively construct the full area name including parent(s)."""
    area = areas[area_id]
    parent_area_id = area["parent_id"]
    if parent_area_id is None:
        # This is the root area, return last area
        return " ".join(labels)

    labels.insert(0, area["name"])
    return _construct_area_name_from_id(areas, parent_area_id, labels)


def enumerate_buttons(
    data: LutronCasetaData,
) -> Iterator[tuple[dict[str, Any], str, bool, DeviceInfo]]:
    """Yield (device, button_name, enabled_default, parent_device_info) per button."""
    bridge = data.bridge
    button_devices = bridge.get_buttons()
    all_devices = bridge.get_devices()
    keypads = data.keypad_data.keypads

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

        yield device, device_name, enabled_default, parent_device_info
