"""."""

from typing import Any

from homeassistant.core import HomeAssistant


async def async_provide_data_source(hass: HomeAssistant, config: dict[str, Any]) -> Any:
    """."""
    return "Source: %s" % config
