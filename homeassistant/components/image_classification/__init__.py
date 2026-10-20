"""The Image classification integration."""

from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes
from homeassistant.helpers.start import async_at_started

from .const import CONF_AI_TASK_ENTITY_ID
from .coordinator import ImageClassificationConfigEntry, ImageClassificationCoordinator
from .taught_frames import TaughtFrames, async_remove_taught_frames

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: ImageClassificationConfigEntry
) -> bool:
    """Set up Image classification from a config entry."""

    def set_source_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_ENTITY_ID: source_entity_id}
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(
                hass, entry.options[CONF_ENTITY_ID]
            ),
            source_entity_id_or_uuid=entry.options[CONF_ENTITY_ID],
        )
    )

    @callback
    def follow_ai_task_entity(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        # A removed entity stays configured, the sensor is unavailable meanwhile.
        if event.data["action"] != "update" or "old_entity_id" not in event.data:
            return
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_AI_TASK_ENTITY_ID: event.data["entity_id"]},
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, entry.options[CONF_AI_TASK_ENTITY_ID], follow_ai_task_entity
        )
    )

    taught_frames = TaughtFrames(hass, entry.entry_id)
    await taught_frames.async_load()
    entry.async_on_unload(taught_frames.close)
    coordinator = ImageClassificationCoordinator(hass, entry, taught_frames)
    # Cameras go offline at times; the sensor is unavailable meanwhile and
    # the options stay usable, like other helpers with a missing source.
    await coordinator.async_refresh()
    if hass.state is not CoreState.running:

        async def refresh_when_started(hass: HomeAssistant) -> None:
            await coordinator.async_refresh()

        entry.async_on_unload(async_at_started(hass, refresh_when_started))
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ImageClassificationConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: ImageClassificationConfigEntry
) -> None:
    """Delete the taught frames of a removed entry."""
    await async_remove_taught_frames(hass, entry.entry_id)
