"""Component to wrap switch entities in entities of other domains."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.homeassistant import exposed_entities
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes

from .const import CONF_INVERT, CONF_TARGET_DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def async_add_to_device(
    hass: HomeAssistant, entry: ConfigEntry, entity_id: str
) -> str | None:
    """Add our config entry to the tracked entity's device."""
    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_id = None

    if (
        not (wrapped_switch := registry.async_get(entity_id))
        or not (device_id := wrapped_switch.device_id)
        or not (device_registry.async_get(device_id))
    ):
        return device_id

    device_registry.async_update_device(device_id, add_config_entry_id=entry.entry_id)

    return device_id


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    entity_registry = er.async_get(hass)
    try:
        entity_id = er.async_validate_entity_id(
            entity_registry, entry.options[CONF_ENTITY_ID]
        )
    except vol.Invalid:
        # The entity is identified by an unknown entity registry ID
        _LOGGER.error(
            "Failed to setup switch_as_x for unknown entity %s",
            entry.options[CONF_ENTITY_ID],
        )
        return False

    def set_source_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_ENTITY_ID: source_entity_id},
        )

    async def source_entity_removed() -> None:
        # The source entity has been removed, we remove the config entry because
        # switch_as_x does not allow replacing the wrapped entity.
        await hass.config_entries.async_remove(entry.entry_id)

    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=async_add_to_device(hass, entry, entity_id),
            source_entity_id_or_uuid=entry.options[CONF_ENTITY_ID],
            source_entity_removed=source_entity_removed,
        )
    )
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))

    await hass.config_entries.async_forward_entry_setups(
        entry, (entry.options[CONF_TARGET_DOMAIN],)
    )
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False
    if config_entry.version == 1:
        options = {**config_entry.options}
        if config_entry.minor_version < 2:
            options.setdefault(CONF_INVERT, False)
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=2
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, (entry.options[CONF_TARGET_DOMAIN],)
    )


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry.

    This will unhide the wrapped entity and restore assistant expose settings.
    """
    registry = er.async_get(hass)
    try:
        switch_entity_id = er.async_validate_entity_id(
            registry, entry.options[CONF_ENTITY_ID]
        )
    except vol.Invalid:
        # The source entity has been removed from the entity registry
        return

    if not (switch_entity_entry := registry.async_get(switch_entity_id)):
        return

    # Unhide the wrapped entity
    if switch_entity_entry.hidden_by == er.RegistryEntryHider.INTEGRATION:
        registry.async_update_entity(switch_entity_id, hidden_by=None)

    switch_as_x_entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    if not switch_as_x_entries:
        return

    switch_as_x_entry = switch_as_x_entries[0]

    # Restore assistant expose settings
    expose_settings = exposed_entities.async_get_entity_settings(
        hass, switch_as_x_entry.entity_id
    )
    for assistant, settings in expose_settings.items():
        if (should_expose := settings.get("should_expose")) is None:
            continue
        exposed_entities.async_expose_entity(
            hass, assistant, switch_entity_id, should_expose
        )
