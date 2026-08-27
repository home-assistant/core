"""The Ouman EH-800 integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import OumanDevice
from .coordinator import OumanEh800ConfigEntry, OumanEh800Coordinator

_PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.VALVE,
]


async def async_setup_entry(hass: HomeAssistant, entry: OumanEh800ConfigEntry) -> bool:
    """Set up Ouman EH-800 from a config entry."""
    coordinator = OumanEh800Coordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    coordinator.sync_circuit_device_names()

    entry.runtime_data = coordinator

    # Register the main device up front so the L1/L2 sub-devices can
    # deterministically resolve their via_device_id, regardless of which
    # platform's entities are added first.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **coordinator.device_info(OumanDevice.MAIN),
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OumanEh800ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
