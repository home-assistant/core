"""The Home Assistant Yellow hardware platform."""
from __future__ import annotations

from homeassistant.components.hardware.models import BoardInfo, HardwareInfo
from homeassistant.components.hassio import get_os_info
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

BOARD_NAME = "Home Assistant Yellow"
MANUFACTURER = "homeassistant"
MODEL = "yellow"


@callback
def async_info(hass: HomeAssistant) -> list[HardwareInfo]:
    """Return board info."""
    if (os_info := get_os_info(hass)) is None:
        raise HomeAssistantError
    board: str | None
    if (board := os_info.get("board")) is None:
        raise HomeAssistantError
    if not board == "yellow":
        raise HomeAssistantError

    return [
        HardwareInfo(
            board=BoardInfo(
                hassio_board_id=board,
                manufacturer=MANUFACTURER,
                model=MODEL,
                revision=None,
            ),
            dongle=None,
            name=BOARD_NAME,
            url=None,
        )
    ]
