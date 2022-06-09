"""The Home Assistant Yellow hardware platform."""
from __future__ import annotations

from homeassistant.components.hardware.models import BoardInfo, HardwareInfo
from homeassistant.components.hassio import get_os_info
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

BOARD_NAMES = {
    "yellow": "Home Assistant Yellow",
}

MODELS = {
    "yellow": "yellow",
}


@callback
def async_info(hass: HomeAssistant) -> HardwareInfo:
    """Return board info."""
    if (os_info := get_os_info(hass)) is None:
        raise HomeAssistantError
    board: str
    if (board := os_info.get("board")) is None:
        raise HomeAssistantError
    if not board == "yellow":
        raise HomeAssistantError

    return HardwareInfo(
        board=BoardInfo(
            hassio_board_id=board,
            manufacturer="homeassistant",
            model=MODELS.get(board),
            revision=None,
        ),
        name=BOARD_NAMES.get(board, f"Unknown Home Assistant model '{board}'"),
        url=None,
    )
