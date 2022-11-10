"""The ClickSend TTS component."""
from homeassistant import config_entries, core
from homeassistant.core import ServiceCall

from .const import DOMAIN, MESSAGE, NOTIFY_SERVICE
from .notify import get_service


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    async def notification(service: ServiceCall) -> None:
        """Send notification via Click Send."""
        message = service.data[MESSAGE]
        ccservice = await get_service(hass, entry.data)
        await ccservice.async_send_message(message)

    hass.services.async_register(
        DOMAIN,
        NOTIFY_SERVICE,
        notification,
    )

    return True
