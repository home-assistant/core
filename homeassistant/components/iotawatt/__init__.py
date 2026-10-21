"""The iotawatt integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .const import CONF_LEGACY_ENERGY, DOMAIN
from .coordinator import IotawattConfigEntry, IotawattUpdater

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IotawattConfigEntry) -> None:
    """Set up iotawatt from a config entry."""
    if entry.options.get(CONF_LEGACY_ENERGY):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"legacy_energy_{entry.entry_id}",
            data={"entry_id": entry.entry_id},
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="legacy_energy",
            translation_placeholders={"name": entry.title},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, f"legacy_energy_{entry.entry_id}")
        _async_remove_legacy_entities(hass, entry)

    coordinator = IotawattUpdater(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: IotawattConfigEntry) -> None:
    """Migrate a config entry."""
    if entry.version == 1:
        # Entries from before the lifetime energy sensors keep the period sensors.
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_LEGACY_ENERGY: True}, version=2
        )


async def async_unload_entry(hass: HomeAssistant, entry: IotawattConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: IotawattConfigEntry) -> None:
    """Remove a config entry."""
    ir.async_delete_issue(hass, DOMAIN, f"legacy_energy_{entry.entry_id}")


@callback
def _async_remove_legacy_entities(
    hass: HomeAssistant, entry: IotawattConfigEntry
) -> None:
    """Remove registry entries of the legacy period energy sensors."""
    entity_registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if reg_entry.unique_id.endswith("-WattHours"):
            entity_registry.async_remove(reg_entry.entity_id)
