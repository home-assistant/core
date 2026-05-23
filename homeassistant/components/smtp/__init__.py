"""The smtp integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_RECIPIENT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery

from .const import DOMAIN, SUBENTRY_TYPE_RECIPIENT


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SMTP from a config entry."""

    # set up legacy notification service
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                **entry.data,
                CONF_NAME: entry.title,
                CONF_RECIPIENT: [
                    subentry.unique_id
                    for subentry in entry.subentries.values()
                    if subentry.subentry_type == SUBENTRY_TYPE_RECIPIENT
                ],
            },
            {},
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, [])

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [])
