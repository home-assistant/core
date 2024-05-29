"""Config flow."""

from homeassistant.core import HomeAssistant


async def _async_has_devices(hass: HomeAssistant) -> bool:
    return True
