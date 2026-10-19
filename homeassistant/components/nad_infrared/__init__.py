"""NAD Infrared integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN

PLATFORMS = [Platform.MEDIA_PLAYER]

# The runtime data is the current entity ID of the infrared emitter.
type NadIrConfigEntry = ConfigEntry[str]


async def async_setup_entry(hass: HomeAssistant, entry: NadIrConfigEntry) -> None:
    """Set up NAD Infrared from a config entry."""
    # The entry stores the emitter's registry ID, which survives renames; resolve
    # it to the current entity ID on every setup.
    if (
        emitter_entity_id := er.async_resolve_entity_id(
            er.async_get(hass), entry.data[CONF_INFRARED_ENTITY_ID]
        )
    ) is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="emitter_not_found"
        )
    entry.runtime_data = emitter_entity_id

    @callback
    def _async_emitter_updated(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Reload when the emitter's entity ID is renamed."""
        data = event.data
        if data["action"] == "update" and "entity_id" in data["changes"]:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, emitter_entity_id, _async_emitter_updated
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: NadIrConfigEntry) -> None:
    """Unload a NAD Infrared config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
