"""Helper functions for the Crownstone integration."""
from __future__ import annotations

from homeassistant.components import usb

from .const import DONT_USE_USB, MANUAL_PATH, REFRESH_LIST


def list_ports_as_str(
    serial_ports: list[usb.USBDevice], no_usb_option: bool = True
) -> list[str]:
    """
    Represent currently available serial ports as string.

    Adds option to not use usb on top of the list,
    option to use manual path or refresh list at the end.
    """
    ports_as_string: list[str] = []

    if no_usb_option:
        ports_as_string.append(DONT_USE_USB)

    for port in serial_ports:
        ports_as_string.append(usb.human_readable_device_name(port))
    ports_as_string.append(MANUAL_PATH)
    ports_as_string.append(REFRESH_LIST)

    return ports_as_string


def map_from_to(val: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    """Map a value from a range to another."""
    return int((val - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)
