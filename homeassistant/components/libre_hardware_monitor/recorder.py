"""Support for LibreHardwareMonitor Recorder Platform."""

from homeassistant.const import UnitOfDataRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, LEGACY_THROUGHPUT_UNIT, THROUGHPUT_UNIQUE_ID_FRAGMENT


@callback
def async_custom_equivalent_units(
    hass: HomeAssistant,
) -> dict[str, dict[str | None, str]]:
    """Return custom equivalent units per entity id.

    Throughput sensors reported the unit as "KB/s" before they got a device class.
    """
    entity_registry = er.async_get(hass)

    return {
        registry_entry.entity_id: {
            LEGACY_THROUGHPUT_UNIT: UnitOfDataRate.KIBIBYTES_PER_SECOND
        }
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if THROUGHPUT_UNIQUE_ID_FRAGMENT in registry_entry.unique_id
    }
