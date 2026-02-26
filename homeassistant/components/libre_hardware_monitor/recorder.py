"""Support for LibreHardwareMonitor Recorder Platform."""

from homeassistant.const import UnitOfDataRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from . import DOMAIN


@callback
def async_custom_equivalent_units(
    hass: HomeAssistant,
) -> dict[str, dict[str | None, str]]:
    """Return custom equivalent units per entity id."""
    lhm_custom_equivalent_units: dict[str, dict[str | None, str]] = {}

    config_entries = hass.config_entries.async_entries(DOMAIN)
    entity_registry = er.async_get(hass)

    for config_entry in config_entries:
        registry_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        throughput_entities = [
            entry for entry in registry_entries if "throughput" in entry.unique_id
        ]
        for registry_entry in throughput_entities:
            lhm_custom_equivalent_units.update(
                {
                    registry_entry.entity_id: {
                        "KB/s": UnitOfDataRate.KILOBYTES_PER_SECOND,
                    }
                }
            )

    return lhm_custom_equivalent_units
