"""The Raspberry Pi hardware platform."""
from __future__ import annotations

from homeassistant.components.hardware.models import HardwareInfo
from homeassistant.core import callback


@callback
def async_info() -> HardwareInfo:
    """Return board info."""
    return {
        "image": "https://images.pexels.com/photos/45201/kitty-cat-kitten-pet-45201.jpeg",
        "name": "Raspberry Pi",
        "url": "https://theuselessweb.com/",
        "type": "board",
    }
