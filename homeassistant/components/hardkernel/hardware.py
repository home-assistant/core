"""The Hardkernel hardware platform."""

from __future__ import annotations

from homeassistant.components.hardware.models import BoardInfo, HardwareInfo
from homeassistant.components.hassio import get_os_info
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

BOARD_NAMES = {
    "odroid-c2": "Hardkernel ODROID-C2",
    "odroid-c4": "Hardkernel ODROID-C4",
    "odroid-m1": "Hardkernel ODROID-M1",
    "odroid-m1s": "Hardkernel ODROID-M1S",
    "odroid-n2": "Home Assistant Blue / Hardkernel ODROID-N2/N2+",
    "odroid-xu4": "Hardkernel ODROID-XU4",
}


@callback
def async_info(hass: HomeAssistant) -> list[HardwareInfo]:
    """Return board info."""
    if (os_info := get_os_info(hass)) is None:
        raise HomeAssistantError
    board: str | None
    if (board := os_info.get("board")) is None:
        raise HomeAssistantError
    if not board.startswith("odroid"):
        raise HomeAssistantError

    config_entries = [
        entry.entry_id for entry in hass.config_entries.async_entries(DOMAIN)
    ]

    return [
        HardwareInfo(
            board=BoardInfo(
                hassio_board_id=board,
                manufacturer=DOMAIN,
                model=board,
                revision=None,
            ),
            config_entries=config_entries,
            dongle=None,
            name=BOARD_NAMES.get(board, f"Unknown hardkernel Odroid model '{board}'"),
            url=None,
        )
    ]
