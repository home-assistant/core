"""The Ouman EH-800 integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .coordinator import OumanEh800ConfigEntry, OumanEh800Coordinator

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.VALVE,
]


async def async_setup_entry(hass: HomeAssistant, entry: OumanEh800ConfigEntry) -> None:
    """Set up Ouman EH-800 from a config entry."""
    coordinator = OumanEh800Coordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    # The L1/L2 child devices reference the main device by id.
    main_device = dr.async_get(hass).async_get_or_create_from_info(
        config_entry_id=entry.entry_id,
        device_info=coordinator.main_device_info,
    )
    coordinator.set_up_circuit_devices(main_device.id)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: OumanEh800ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
