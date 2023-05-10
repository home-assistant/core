"""The Raspberry Pi hardware platform."""
from __future__ import annotations

from homeassistant.components.hardware.models import BoardInfo, HardwareInfo
from homeassistant.components.hassio import get_os_info
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

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

MODELS = {
    "rpi": "1",
    "rpi0": "zero",
    "rpi0-w": "zero_w",
    "rpi2": "2",
    "rpi3": "3",
    "rpi3-64": "3",
    "rpi4": "4",
    "rpi4-64": "4",
}


@callback
def async_info(hass: HomeAssistant) -> list[HardwareInfo]:
    """Return board info."""
    if (os_info := get_os_info(hass)) is None:
        raise HomeAssistantError
    board: str | None
    if (board := os_info.get("board")) is None:
        raise HomeAssistantError
    if not board.startswith("rpi"):
        raise HomeAssistantError

    config_entries = [
        entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN)
    ]

    return [
        HardwareInfo(
            board=BoardInfo(
                hassio_board_id=board,
                manufacturer=DOMAIN,
                model=MODELS.get(board),
                revision=None,
            ),
            config_entries=config_entries,
            dongle=None,
            name=BOARD_NAMES.get(board, f"Unknown Raspberry Pi model '{board}'"),
            url=None,
        )
    ]
