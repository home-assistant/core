"""The free_mobile component."""

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.util import slugify

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Free Mobile from a config entry."""

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                **entry.data,
                CONF_NAME: entry.title,
                "entry_id": entry.entry_id,
            },
            {},
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    The legacy notify platform skips re-registering a service that is already
    present, so the previous FreeSMSNotificationService (and its stale access
    token) would otherwise stay in place until Home Assistant is restarted.
    Removing our own service by name lets async_setup_entry register a fresh
    one, without touching other notify integrations' services.
    """
    hass.services.async_remove(NOTIFY_DOMAIN, slugify(entry.title))
    return True
