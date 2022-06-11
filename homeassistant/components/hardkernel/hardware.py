"""The Hardkernel hardware platform."""
from __future__ import annotations

from homeassistant.components.hardware.models import BoardInfo, HardwareInfo
from homeassistant.components.hassio import get_os_info
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

BOARD_NAMES = {
    "odroid-c2": "Hardkernel Odroid-C2",
    "odroid-c4": "Hardkernel Odroid-C4",
    "odroid-n2": "Home Assistant Blue / Hardkernel Odroid-N2",
    "odroid-xu4": "Hardkernel Odroid-XU4",
}


@callback
def async_info(hass: HomeAssistant) -> HardwareInfo:
    """Return board info."""
    if (os_info := get_os_info(hass)) is None:
        raise HomeAssistantError
    board: str
    if (board := os_info.get("board")) is None:
        raise HomeAssistantError
    if not board.startswith("odroid"):
        raise HomeAssistantError

    return HardwareInfo(
        board=BoardInfo(
            hassio_board_id=board,
            manufacturer=DOMAIN,
            model=board,
            revision=None,
        ),
        name=BOARD_NAMES.get(board, f"Unknown hardkernel Odroid model '{board}'"),
        url=None,
    )
