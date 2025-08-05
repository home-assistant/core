"""Calculates mold growth indication from temperature and humidity."""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device import (
    async_entity_id_to_device_id,
    async_remove_stale_devices_links_keep_entity_device,
)
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
    async_remove_helper_config_entry_from_source_device,
)

from .const import CONF_INDOOR_HUMIDITY, CONF_INDOOR_TEMP, CONF_OUTDOOR_TEMP

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mold indicator from a config entry."""

    # This can be removed in HA Core 2026.2
    async_remove_stale_devices_links_keep_entity_device(
        hass, entry.entry_id, entry.options[CONF_INDOOR_HUMIDITY]
    )

    def set_source_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_INDOOR_HUMIDITY: source_entity_id},
        )

    entry.async_on_unload(
        # We use async_handle_source_entity_changes to track changes to the humidity
        # sensor, but not the temperature sensors because the mold_indicator links
        # to the humidity sensor's device.
        async_handle_source_entity_changes(
            hass,
            add_helper_config_entry_to_device=False,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(
                hass, entry.options[CONF_INDOOR_HUMIDITY]
            ),
            source_entity_id_or_uuid=entry.options[CONF_INDOOR_HUMIDITY],
        )
    )

    for temp_sensor in (CONF_INDOOR_TEMP, CONF_OUTDOOR_TEMP):

        def get_temp_sensor_updater(
            temp_sensor: str,
        ) -> Callable[[Event[er.EventEntityRegistryUpdatedData]], None]:
            """Return a function to update the config entry with the new temp sensor."""

            @callback
            def async_sensor_updated(
                event: Event[er.EventEntityRegistryUpdatedData],
            ) -> None:
                """Handle entity registry update."""
                data = event.data
                if data["action"] != "update":
                    return
                if "entity_id" not in data["changes"]:
                    return

                # Entity_id changed, update the config entry
                hass.config_entries.async_update_entry(
                    entry,
                    options={**entry.options, temp_sensor: data["entity_id"]},
                )

            return async_sensor_updated

        entry.async_on_unload(
            async_track_entity_registry_updated_event(
                hass, entry.options[temp_sensor], get_temp_sensor_updater(temp_sensor)
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Mold indicator config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


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
            # Remove the mold indicator config entry from the source device
            if source_device_id := async_entity_id_to_device_id(
                hass, config_entry.options[CONF_INDOOR_HUMIDITY]
            ):
                async_remove_helper_config_entry_from_source_device(
                    hass,
                    helper_config_entry_id=config_entry.entry_id,
                    source_device_id=source_device_id,
                )
            hass.config_entries.async_update_entry(
                config_entry, version=1, minor_version=2
            )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
