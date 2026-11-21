"""The Ceiling Fan Infrared integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_entity_registry_updated_event

from .const import CONF_INFRARED_ENTITY_ID, CONF_INFRARED_ENTITY_UUID

PLATFORMS: list[Platform] = [Platform.FAN]


def _resolve_emitter_entity_id(
    entity_registry: er.EntityRegistry, entry: ConfigEntry
) -> str:
    """Resolve the stored emitter reference to its current entity ID.

    The registry UUID is preferred because it survives renames, including
    renames that happen while this entry is unloaded. Entries created before the
    UUID was stored, and emitters without a registry entry, fall back to the
    stored entity ID.
    """
    entity_id: str = entry.data[CONF_INFRARED_ENTITY_ID]
    if uuid := entry.data.get(CONF_INFRARED_ENTITY_UUID):
        if (resolved := er.async_resolve_entity_id(entity_registry, uuid)) is not None:
            entity_id = resolved
    return entity_id


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Ceiling Fan Infrared from a config entry."""
    entity_registry = er.async_get(hass)
    emitter_entity_id = _resolve_emitter_entity_id(entity_registry, entry)
    data = {**entry.data, CONF_INFRARED_ENTITY_ID: emitter_entity_id}

    if (
        CONF_INFRARED_ENTITY_UUID not in data
        and (registry_entry := entity_registry.async_get(emitter_entity_id)) is not None
    ):
        # Remember the emitter by its registry UUID, so a rename is followed
        # even when it happens while this entry is unloaded.
        data[CONF_INFRARED_ENTITY_UUID] = registry_entry.id

    if data != entry.data:
        hass.config_entries.async_update_entry(entry, data=data)

    async def async_emitter_renamed(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Follow the emitter when its entity ID changes."""
        event_data = event.data
        if event_data["action"] != "update" or "entity_id" not in event_data["changes"]:
            return
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_INFRARED_ENTITY_ID: event_data["entity_id"]},
        )
        # The fan entity binds to the emitter at setup, so reload it to rebind.
        # Its state is restored, so the reload does not reset the assumed state.
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, emitter_entity_id, async_emitter_renamed
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
