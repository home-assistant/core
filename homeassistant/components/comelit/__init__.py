"""Comelit integration."""


from aiocomelit.const import BRIDGE

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT, DOMAIN
from .coordinator import ComelitBaseCoordinator, ComelitSerialBridge, ComelitVedoSystem

BRIDGE_PLATFORMS = [
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
VEDO_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Comelit platform."""

    coordinator: ComelitBaseCoordinator
    if entry.data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        coordinator = ComelitSerialBridge(
            hass,
            entry.data[CONF_HOST],
            entry.data.get(CONF_PORT, DEFAULT_PORT),
            entry.data[CONF_PIN],
        )
        platforms = BRIDGE_PLATFORMS
    else:
        coordinator = ComelitVedoSystem(
            hass,
            entry.data[CONF_HOST],
            entry.data.get(CONF_PORT, DEFAULT_PORT),
            entry.data[CONF_PIN],
        )
        platforms = VEDO_PLATFORMS

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if entry.data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        return await _async_unload_bridge_entry(hass, entry)

    return await _async_unload_vedo_entry(hass, entry)


async def _async_unload_bridge_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Comelit Serial Bridge entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, BRIDGE_PLATFORMS
    ):
        coordinator: ComelitSerialBridge = hass.data[DOMAIN][entry.entry_id]
        await coordinator.api.logout()
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_unload_vedo_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Comelit VEDO system entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, VEDO_PLATFORMS
    ):
        coordinator: ComelitVedoSystem = hass.data[DOMAIN][entry.entry_id]
        await coordinator.api.logout()
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
