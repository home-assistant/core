"""The Ceiling Fan Infrared integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from .const import CONF_INFRARED_ENTITY_ID

PLATFORMS: list[Platform] = [Platform.FAN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Ceiling Fan Infrared from a config entry."""

    async def async_emitter_renamed(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Update the entry when the emitter entity ID changes."""
        data = event.data
        if data["action"] != "update" or "entity_id" not in data["changes"]:
            return
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_INFRARED_ENTITY_ID: data["entity_id"]},
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, entry.data[CONF_INFRARED_ENTITY_ID], async_emitter_renamed
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
