"""The Local vision integration."""

from tarsius import BackendError, NcnnBackend

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import DOMAIN

PLATFORMS = [Platform.AI_TASK]

type LocalVisionConfigEntry = ConfigEntry[NcnnBackend]


async def async_setup_entry(hass: HomeAssistant, entry: LocalVisionConfigEntry) -> bool:
    """Set up Local vision from a config entry."""
    try:
        entry.runtime_data = await hass.async_add_executor_job(NcnnBackend)
    except BackendError as err:
        # The model ships with tarsius, retrying won't bring it back.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="model_unavailable",
            translation_placeholders={"error": str(err)},
        ) from err
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LocalVisionConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
