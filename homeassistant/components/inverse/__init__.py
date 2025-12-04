"""Component to invert entities."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.homeassistant import exposed_entities
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VALVE,
]


@callback
def async_get_parent_device_id(hass: HomeAssistant, entity_id: str) -> str | None:
    """Get the parent device id."""
    registry = er.async_get(hass)

    if not (wrapped_entity := registry.async_get(entity_id)):
        return None

    return wrapped_entity.device_id


@callback
def async_get_parent_device_platform(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the platform/domain for the wrapped entity.

    Always derive from the entity_id domain to ensure we forward to real platforms
    (avoid test platform names from registry fixtures).
    """
    if "." in entity_id:
        return entity_id.split(".", 1)[0]
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    entity_registry = er.async_get(hass)
    try:
        entity_id = er.async_validate_entity_id(
            entity_registry, entry.data[CONF_ENTITY_ID]
        )
    except vol.Invalid:
        # The entity is identified by an unknown entity registry ID
        _LOGGER.error(
            "Failed to setup inverse for unknown entity %s",
            entry.data[CONF_ENTITY_ID],
        )
        return False

    platform = async_get_parent_device_platform(hass, entity_id)
    if platform is None:
        _LOGGER.error(
            "Failed to determine platform for entity %s",
            entity_id,
        )
        return False

    def set_source_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_ENTITY_ID: source_entity_id},
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    async def source_entity_removed() -> None:
        # The source entity has been removed, we remove the config entry because
        # inverse does not allow replacing the wrapped entity.
        await hass.config_entries.async_remove(entry.entry_id)

    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            add_helper_config_entry_to_device=False,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=async_get_parent_device_id(hass, entity_id),
            source_entity_id_or_uuid=entry.data[CONF_ENTITY_ID],
            source_entity_removed=source_entity_removed,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, [platform])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    platform = async_get_parent_device_platform(hass, entry.data[CONF_ENTITY_ID])
    if platform is None:
        return True
    return await hass.config_entries.async_unload_platforms(entry, [platform])


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry.

    This will unhide the wrapped entity and restore assistant expose settings.
    """
    registry = er.async_get(hass)
    try:
        source_entity_id = er.async_validate_entity_id(
            registry, entry.data[CONF_ENTITY_ID]
        )
    except vol.Invalid:
        # The source entity has been removed from the entity registry
        return

    if not (source_entity_entry := registry.async_get(source_entity_id)):
        return

    # Unhide the wrapped entity
    if source_entity_entry.hidden_by == er.RegistryEntryHider.INTEGRATION:
        registry.async_update_entity(source_entity_id, hidden_by=None)

    inverse_entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    if not inverse_entries:
        return

    inverse_entry = inverse_entries[0]
    # Restore assistant expose settings
    expose_settings = exposed_entities.async_get_entity_settings(
        hass, inverse_entry.entity_id
    )
    for assistant, settings in expose_settings.items():
        if (should_expose := settings.get("should_expose")) is None:
            continue
        exposed_entities.async_expose_entity(
            hass, assistant, source_entity_id, should_expose
        )
