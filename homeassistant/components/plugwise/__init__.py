"""Plugwise platform for Home Assistant Core."""

from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, PLATFORMS
from .coordinator import PlugwiseConfigEntry, PlugwiseDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: PlugwiseConfigEntry) -> bool:
    """Set up Plugwise components from a config entry."""
    await er.async_migrate_entries(hass, entry.entry_id, async_migrate_entity_entry)

    coordinator = PlugwiseDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(coordinator.api.gateway_id))},
        manufacturer="Plugwise",
        model=coordinator.api.smile.model,
        model_id=coordinator.api.smile.model_id,
        name=coordinator.api.smile.name,
        sw_version=str(coordinator.api.smile.version),
    )  # required for adding the entity-less P1 Gateway

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlugwiseConfigEntry) -> bool:
    """Unload the Plugwise components."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def async_migrate_entity_entry(entry: er.RegistryEntry) -> dict[str, Any] | None:
    """Migrate Plugwise entity entries to new unique IDs."""
    if entry.domain == Platform.CLIMATE and entry.unique_id.endswith("-climate"):
        return {"new_unique_id": entry.unique_id.replace("-climate", "-thermostat")}

    if entry.domain == Platform.BINARY_SENSOR and entry.unique_id.endswith(
        "-slave_boiler_state"
    ):
        return {
            "new_unique_id": entry.unique_id.replace(
                "-slave_boiler_state", "-secondary_boiler_state"
            )
        }

    if entry.domain == Platform.SENSOR and entry.unique_id.endswith(
        "-relative_humidity"
    ):
        return {
            "new_unique_id": entry.unique_id.replace("-relative_humidity", "-humidity")
        }

    if entry.domain == Platform.SWITCH and entry.unique_id.endswith("-plug"):
        return {"new_unique_id": entry.unique_id.replace("-plug", "-relay")}

    # No migration needed
    return None
