"""Comelit integration."""

from aiocomelit.const import BRIDGE

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT, DOMAIN
from .coordinator import ComelitBaseCoordinator, ComelitSerialBridge, ComelitVedoSystem

BRIDGE_PLATFORMS = [
    Platform.CLIMATE,
    Platform.COVER,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]
VEDO_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.SENSOR,
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
        platforms = BRIDGE_PLATFORMS
    else:
        platforms = VEDO_PLATFORMS

    coordinator: ComelitBaseCoordinator = hass.data[DOMAIN][entry.entry_id]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        await coordinator.api.logout()
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
