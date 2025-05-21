"""The Leneda integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_ENERGY_ID, CONF_METERING_POINTS, DOMAIN
from .coordinator import LenedaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type LenedaConfigEntry = ConfigEntry[LenedaCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LenedaConfigEntry) -> bool:
    """Set up Leneda from a config entry."""
    coordinator = LenedaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LenedaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a metering point when a device is deleted."""
    # Find our DOMAIN‐scoped identifier: "{energy_id}_{metering_point}"
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        energy_id = config_entry.data.get(CONF_ENERGY_ID)
        prefix = f"{energy_id}_"
        if identifier.startswith(prefix):
            metering_point = identifier[len(prefix) :]
            # Remove it from CONF_METERING_POINTS
            pts = list(config_entry.data.get(CONF_METERING_POINTS, []))
            if metering_point in pts:
                pts.remove(metering_point)
            # Drop its sensors
            sels = dict(config_entry.options.get("selected_sensors", {}))
            sels.pop(metering_point, None)
            # Commit update and reload entry
            hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    CONF_METERING_POINTS: pts,
                },
                options={
                    **dict(config_entry.options or {}),
                    "selected_sensors": sels,
                },
            )
            await hass.config_entries.async_reload(config_entry.entry_id)
            return True
    return False
