"""Plugwise platform for Home Assistant Core."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import PlugwiseDataUpdateCoordinator

type PlugwiseConfigEntry = ConfigEntry[PlugwiseDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PlugwiseConfigEntry) -> bool:
    """Set up Plugwise components from a config entry."""
    await er.async_migrate_entries(hass, entry.entry_id, async_migrate_entity_entry)

    coordinator = PlugwiseDataUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    migrate_sensor_entities(hass, coordinator)

    entry.runtime_data = coordinator

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(coordinator.api.gateway_id))},
        manufacturer="Plugwise",
        model=coordinator.api.smile_model,
        name=coordinator.api.smile_name,
        sw_version=coordinator.api.smile_version[0],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PlugwiseConfigEntry) -> bool:
    """Unload the Plugwise components."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def async_migrate_entity_entry(entry: er.RegistryEntry) -> dict[str, Any] | None:
    """Migrate Plugwise entity entries.

    - Migrates old unique ID's from old binary_sensors and switches to the new unique ID's
    """
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


def migrate_sensor_entities(
    hass: HomeAssistant,
    coordinator: PlugwiseDataUpdateCoordinator,
) -> None:
    """Migrate Sensors if needed."""
    ent_reg = er.async_get(hass)

    # Migrating opentherm_outdoor_temperature
    # to opentherm_outdoor_air_temperature sensor
    for device_id, device in coordinator.data.devices.items():
        if device.get("dev_class") != "heater_central":
            continue

        old_unique_id = f"{device_id}-outdoor_temperature"
        if entity_id := ent_reg.async_get_entity_id(
            Platform.SENSOR, DOMAIN, old_unique_id
        ):
            new_unique_id = f"{device_id}-outdoor_air_temperature"
            LOGGER.debug(
                "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
                entity_id,
                old_unique_id,
                new_unique_id,
            )
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
