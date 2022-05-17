"""The Raspberry Pi hardware platform."""
from __future__ import annotations

from homeassistant.components.hardware.models import HardwareInfo
from homeassistant.components.hassio import get_os_info
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

BOARD_NAMES = {
    "rpi": "Raspberry Pi",
    "rpi0": "Raspberry Pi Zero",
    "rpi0-w": "Raspberry Pi Zero W",
    "rpi2": "Raspberry Pi 2",
    "rpi3": "Raspberry Pi 3 (32-bit)",
    "rpi3-64": "Raspberry Pi 3",
    "rpi4": "Raspberry Pi 4 (32-bit)",
    "rpi4-64": "Raspberry Pi 4",
}


@callback
def async_info(hass: HomeAssistant) -> HardwareInfo:
    """Return board info."""
    if (os_info := get_os_info(hass)) is None:
        raise HomeAssistantError
    board: str
    if (board := os_info.get("board")) is None:
        raise HomeAssistantError
    if not board.startswith("rpi"):
        raise HomeAssistantError

    return HardwareInfo(
        image="https://images.pexels.com/photos/45201/kitty-cat-kitten-pet-45201.jpeg",
        name=BOARD_NAMES.get(board, f"Unknown Raspberry Pi model '{board}'"),
        url="https://theuselessweb.com/",
        type="board",
    )
