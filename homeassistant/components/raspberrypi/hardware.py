"""The Raspberry Pi hardware platform."""
from __future__ import annotations

from homeassistant.components.hardware.models import BoardInfo
from homeassistant.core import callback


@callback
def async_board_info() -> BoardInfo:
    """Return board info."""
    return {
        "name": "Raspberry Pi",
        "url": "https://theuselessweb.com/",
        "image": "https://images.pexels.com/photos/45201/kitty-cat-kitten-pet-45201.jpeg",
    }
