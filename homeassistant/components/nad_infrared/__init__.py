"""NAD Infrared integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from .const import CONF_INFRARED_ENTITY_ID

PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up NAD Infrared from a config entry."""

    @callback
    def _async_emitter_updated(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Follow the infrared emitter when its entity ID is renamed."""
        data = event.data
        if data["action"] != "update" or "entity_id" not in data["changes"]:
            return
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_INFRARED_ENTITY_ID: data["entity_id"]}
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, entry.data[CONF_INFRARED_ENTITY_ID], _async_emitter_updated
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a NAD Infrared config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
