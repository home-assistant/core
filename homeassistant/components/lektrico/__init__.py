"""The Lektrico Charging Station integration."""

from __future__ import annotations

from lektricowifi import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_SERIAL_NUMBER, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LektricoDeviceDataUpdateCoordinator

# List the platforms that charger supports.
CHARGERS_PLATFORMS = [Platform.SENSOR]

# List the platforms that load balancer device supports.
LB_DEVICES_PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lektrico Charging Station from a config entry."""
    coordinator = LektricoDeviceDataUpdateCoordinator(
        hass,
        f"{entry.data[CONF_TYPE]}_{entry.data[ATTR_SERIAL_NUMBER]}",
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _get_platforms(entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, _get_platforms(entry)
    ):
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


def _get_platforms(entry: ConfigEntry) -> list[Platform]:
    """Return the platforms for this type of device."""
    _device_type: str = entry.data[CONF_TYPE]
    if _device_type in (Device.TYPE_1P7K, Device.TYPE_3P22K):
        return CHARGERS_PLATFORMS
    return LB_DEVICES_PLATFORMS
