"""The Local vision integration."""

from tarsius import BackendError

from homeassistant.const import CONF_ENTITY_ID, CONF_REGION, Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN
from .coordinator import LocalVisionConfigEntry, LocalVisionCoordinator
from .detection import async_create_detector
from .taught_frames import TaughtFrames, async_remove_taught_frames

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LocalVisionConfigEntry) -> None:
    """Set up Local vision from a config entry."""

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

    try:
        taught_frames = await _async_load_taught_frames(hass, entry)
    except BackendError as err:
        # The model ships with tarsius, retrying won't bring it back.
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="model_unavailable",
            translation_placeholders={"error": str(err)},
        ) from err
    entry.async_on_unload(taught_frames.close)
    coordinator = LocalVisionCoordinator(hass, entry, taught_frames)
    # Cameras go offline at times; the sensor is unavailable meanwhile and
    # the options stay usable, like other helpers with a missing source.
    await coordinator.async_refresh()
    if hass.state is not CoreState.running:

        async def refresh_when_started(hass: HomeAssistant) -> None:
            await coordinator.async_refresh()

        entry.async_on_unload(async_at_started(hass, refresh_when_started))
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_load_taught_frames(
    hass: HomeAssistant, entry: LocalVisionConfigEntry
) -> TaughtFrames:
    detector = await async_create_detector(hass, entry.options[CONF_REGION])
    taught_frames = TaughtFrames(hass, entry.entry_id, detector)
    await taught_frames.async_load()
    return taught_frames


async def async_unload_entry(
    hass: HomeAssistant, entry: LocalVisionConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: LocalVisionConfigEntry
) -> None:
    """Delete the taught frames of a removed entry."""
    await async_remove_taught_frames(hass, entry.entry_id)
