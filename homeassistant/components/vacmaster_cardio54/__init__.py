"""The Vacmaster Cardio54 integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import CONF_TRANSMITTER

PLATFORMS: list[Platform] = [Platform.FAN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vacmaster Cardio54 from a config entry."""
    # Fail fast if the configured transmitter is no longer in the entity
    # registry — without it the fan can never reach its hardware. Raising
    # ``ConfigEntryNotReady`` keeps HA retrying so a re-loaded transmitter
    # integration recovers automatically; the user sees a clear error state
    # in the UI in the meantime.
    if er.async_get(hass).async_get(entry.data[CONF_TRANSMITTER]) is None:
        raise ConfigEntryNotReady(
            f"Configured transmitter {entry.data[CONF_TRANSMITTER]} no longer "
            "exists in the entity registry"
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
