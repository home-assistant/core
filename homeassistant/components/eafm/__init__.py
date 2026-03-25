"""UK Environment Agency Flood Monitoring Integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import EafmConfigEntry, EafmCoordinator

PLATFORMS = [Platform.SENSOR]


def _fix_device_registry_identifiers(
    hass: HomeAssistant, entry: EafmConfigEntry
) -> None:
    """Fix invalid identifiers in device registry.

    Added in 2026.4, can be removed in 2026.10 or later.
    """
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        old_identifier = (DOMAIN, "measure-id", entry.data["station"])
        if old_identifier not in device_entry.identifiers:  # type: ignore[comparison-overlap]
            continue
        new_identifiers = device_entry.identifiers.copy()
        new_identifiers.discard(old_identifier)  # type: ignore[arg-type]
        new_identifiers.add((DOMAIN, entry.data["station"]))
        device_registry.async_update_device(
            device_entry.id, new_identifiers=new_identifiers
        )


async def async_setup_entry(hass: HomeAssistant, entry: EafmConfigEntry) -> bool:
    """Set up flood monitoring sensors for this config entry."""
    _fix_device_registry_identifiers(hass, entry)
    coordinator = EafmCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EafmConfigEntry) -> bool:
    """Unload flood monitoring sensors."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
