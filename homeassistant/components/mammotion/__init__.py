"""The Mammotion Luba integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_ACCOUNTNAME,
    CONF_AEP_DATA,
    CONF_AUTH_DATA,
    CONF_CONNECT_DATA,
    CONF_DEVICE_DATA,
    CONF_REGION_DATA,
    CONF_RETRY_COUNT,
    CONF_SESSION_DATA,
    CONF_USE_WIFI,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
)
from .coordinator import MammotionDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LAWN_MOWER,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]

type MammotionConfigEntry = ConfigEntry[MammotionDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> bool:
    """Set up Mammotion Luba from a config entry."""
    assert entry.unique_id is not None

    if CONF_ADDRESS not in entry.data and CONF_MAC in entry.data:
        # Bleak uses addresses not mac addresses which are actually
        # UUIDs on some platforms (MacOS).
        mac = entry.data[CONF_MAC]
        if "-" not in mac:
            mac = dr.format_mac(mac)
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_ADDRESS: mac},
        )

    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT},
        )

    mammotion_coordinator = MammotionDataUpdateCoordinator(hass, entry)
    await mammotion_coordinator.async_setup()

    await mammotion_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = mammotion_coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.manager.remove_device(entry.runtime_data.device_name)
    return unload_ok
