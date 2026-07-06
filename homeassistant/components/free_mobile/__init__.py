"""The free_mobile component."""

from freesms import FreeClient

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.util import slugify

from .const import DOMAIN

type FreeMobileConfigEntry = ConfigEntry[FreeClient]


async def async_setup_entry(hass: HomeAssistant, entry: FreeMobileConfigEntry) -> bool:
    """Set up Free Mobile from a config entry."""

    entry.runtime_data = FreeClient(
        entry.data[CONF_USERNAME], entry.data[CONF_ACCESS_TOKEN]
    )

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_NAME: entry.title, "entry_id": entry.entry_id},
            {},
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreeMobileConfigEntry) -> bool:
    """Unload a config entry."""
    hass.services.async_remove(NOTIFY_DOMAIN, slugify(entry.title))
    return True
