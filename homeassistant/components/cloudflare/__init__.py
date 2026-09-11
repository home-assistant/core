"""Update the IP addresses of your Cloudflare DNS records."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import CloudflareConfigEntry, CloudflareCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Cloudflare."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: CloudflareConfigEntry) -> bool:
    """Set up Cloudflare from a config entry."""
    entry.runtime_data = CloudflareCoordinator(hass, entry)
    await entry.runtime_data.async_config_entry_first_refresh()

    # Since we are not using coordinator for data reads, we need to add dummy listener
    entry.async_on_unload(entry.runtime_data.async_add_listener(lambda: None))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CloudflareConfigEntry) -> bool:
    """Unload Cloudflare config entry."""

    return True
