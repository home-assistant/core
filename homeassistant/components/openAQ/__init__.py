from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers import device_registry
from .const import (
    DOMAIN
)


# async def async_setup(hass: HomeAssistant, config: Config) -> bool:
#     """Read configuration from yaml."""

#     pass


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration from config entry."""
    dr = device_registry.async_get(hass)

    """ Create OpenAQ Device """
    dr.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "entry")},
        name="brb",
        model="Unknown",
    )
    hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "sensor")
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    return True
