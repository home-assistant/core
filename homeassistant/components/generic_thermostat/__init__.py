"""The generic_thermostat component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device import (
    async_entity_id_to_device_id,
    async_remove_stale_devices_links_keep_entity_device,
)
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes

from .const import CONF_HEATER, CONF_SENSOR, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""

    async_remove_stale_devices_links_keep_entity_device(
        hass,
        entry.entry_id,
        entry.options[CONF_HEATER],
    )

    def set_humidifier_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_HEATER: source_entity_id},
        )

    async def source_entity_removed() -> None:
        # The source entity has been removed, we need to clean the device links.
        async_remove_stale_devices_links_keep_entity_device(hass, entry.entry_id, None)

    entry.async_on_unload(
        # We use async_handle_source_entity_changes to track changes to the heater, but
        # not the temperature sensor because the generic_hygrostat adds itself to the
        # heater's device.
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_humidifier_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(
                hass, entry.options[CONF_HEATER]
            ),
            source_entity_id_or_uuid=entry.options[CONF_HEATER],
            source_entity_removed=source_entity_removed,
        )
    )

    async def async_sensor_updated(
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
            options={**entry.options, CONF_SENSOR: data["entity_id"]},
        )

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, entry.options[CONF_SENSOR], async_sensor_updated
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
