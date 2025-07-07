"""The signalmessenger component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .notify import get_service


def _get_service_name(entry: ConfigEntry):
    return ("notify", f"signal_{entry.data[CONF_NAME]}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    notify_service = await hass.async_add_executor_job(
        get_service, hass, dict(entry.data.items()), None
    )
    service_domain, service_name = _get_service_name(entry)
    await notify_service.async_setup(hass, service_name, service_domain)
    await notify_service.async_register_services()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    service_domain, service_name = _get_service_name(entry)
    hass.services.async_remove(service_domain, service_name)
    return True
