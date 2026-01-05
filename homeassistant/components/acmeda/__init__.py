"""The Rollease Acmeda Automate integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .hub import PulseHub

CONF_HUBS = "hubs"

PLATFORMS = [Platform.COVER, Platform.SENSOR]

type AcmedaConfigEntry = ConfigEntry[PulseHub]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: AcmedaConfigEntry
) -> bool:
    """Set up Rollease Acmeda Automate hub from a config entry."""

    await _migrate_unique_ids(hass, config_entry)

    hub = PulseHub(hass, config_entry)

    if not await hub.async_setup():
        return False

    config_entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def _migrate_unique_ids(hass: HomeAssistant, entry: AcmedaConfigEntry) -> None:
    """Migrate pre-config flow unique ids."""
    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    for reg_entry in registry_entries:
        if isinstance(reg_entry.unique_id, int):  # type: ignore[unreachable]
            entity_registry.async_update_entity(  # type: ignore[unreachable]
                reg_entry.entity_id, new_unique_id=str(reg_entry.unique_id)
            )


async def async_unload_entry(
    hass: HomeAssistant, config_entry: AcmedaConfigEntry
) -> bool:
    """Unload a config entry."""
    hub = config_entry.runtime_data

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if not await hub.async_reset():
        return False

    return unload_ok
