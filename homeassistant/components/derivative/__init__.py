"""The Derivative integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SOURCE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import (
    async_entity_id_to_device_id,
    async_remove_stale_devices_links_keep_entity_device,
)
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
    async_remove_helper_config_entry_from_source_device,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Derivative from a config entry."""

    # This can be removed in HA Core 2026.2
    async_remove_stale_devices_links_keep_entity_device(
        hass, entry.entry_id, entry.options[CONF_SOURCE]
    )

    def set_source_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_SOURCE: source_entity_id},
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            add_helper_config_entry_to_device=False,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(
                hass, entry.options[CONF_SOURCE]
            ),
            source_entity_id_or_uuid=entry.options[CONF_SOURCE],
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, (Platform.SENSOR,))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, (Platform.SENSOR,))


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        if config_entry.minor_version < 2:
            new_options = {**config_entry.options}

            if new_options.get("unit_prefix") == "none":
                # Before we had support for optional selectors, "none" was used for selecting nothing
                del new_options["unit_prefix"]

            hass.config_entries.async_update_entry(
                config_entry, options=new_options, version=1, minor_version=2
            )

        if config_entry.minor_version < 3:
            # Remove the derivative config entry from the source device
            if source_device_id := async_entity_id_to_device_id(
                hass, config_entry.options[CONF_SOURCE]
            ):
                async_remove_helper_config_entry_from_source_device(
                    hass,
                    helper_config_entry_id=config_entry.entry_id,
                    source_device_id=source_device_id,
                )
            hass.config_entries.async_update_entry(
                config_entry, version=1, minor_version=3
            )

        if config_entry.minor_version < 4:
            # Ensure we use the correct units
            new_options = {**config_entry.options}

            if new_options.get("unit_prefix") == "\u00b5":
                # Ensure we use the preferred coding of μ
                new_options["unit_prefix"] = "\u03bc"

            hass.config_entries.async_update_entry(
                config_entry, options=new_options, version=1, minor_version=4
            )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
