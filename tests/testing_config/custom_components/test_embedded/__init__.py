"""Component with embedded platforms."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "test_embedded"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Mock config."""
    return True
