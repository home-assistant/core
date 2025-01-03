"""The Appwrite integration."""

from __future__ import annotations

from appwrite.client import AppwriteException

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .appwrite import AppwriteClient, AppwriteConfigEntry
from .const import DOMAIN
from .services import AppwriteServices


async def async_setup_entry(
    hass: HomeAssistant, config_entry: AppwriteConfigEntry
) -> bool:
    """Save user data in Appwrite config entry and init services."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = config_entry.data

    # Set runtime data
    appwrite_client = AppwriteClient(dict(config_entry.data))

    try:
        appwrite_client.async_validate_credentials()
    except AppwriteException as ae:
        raise ConfigEntryAuthFailed("Invalid credentials") from ae

    config_entry.runtime_data = appwrite_client

    # Setup services
    services = AppwriteServices(hass, config_entry)
    await services.setup()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AppwriteConfigEntry) -> bool:
    """Unload services and config entry."""

    for service in hass.services.async_services_for_domain(DOMAIN):
        hass.services.async_remove(DOMAIN, service)

    hass.data[DOMAIN].pop(entry.entry_id)
    return True
