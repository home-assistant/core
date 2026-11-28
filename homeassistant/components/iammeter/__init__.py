"""IAMMETER integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN
from .coordinator import IammeterConfigEntry, IammeterDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]


def migrate_pf_unit(registry: er.EntityRegistry, entity: er.RegistryEntry) -> None:
    """Reset the implicit PF unit while preserving an explicit user preference."""
    if "unit_of_measurement" not in entity.options.get("sensor", {}):
        registry.async_update_entity_options(
            entity.entity_id,
            "sensor.private",
            {
                **entity.options.get("sensor.private", {}),
                "suggested_unit_of_measurement": None,
            },
        )


async def async_migrate_entry(hass: HomeAssistant, entry: IammeterConfigEntry) -> None:
    """Migrate the default PF display, preserving explicit unit preferences."""
    if entry.minor_version < 2:
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if (
                entity.original_device_class == "power_factor"
                or entity.unique_id.startswith(f"{entry.unique_id}_PF_")
            ):
                migrate_pf_unit(registry, entity)
        hass.config_entries.async_update_entry(entry, minor_version=2)


async def async_setup_entry(hass: HomeAssistant, entry: IammeterConfigEntry) -> None:
    """Set up IAMMETER from a config entry."""
    coordinator = IammeterDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: IammeterConfigEntry) -> None:
    """Unload an IAMMETER config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
