"""Comelit integration."""

from aiocomelit.const import BRIDGE

from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT
from .coordinator import (
    ComelitBaseCoordinator,
    ComelitConfigEntry,
    ComelitSerialBridge,
    ComelitVedoSystem,
)
from .utils import async_client_session

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
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ComelitConfigEntry) -> bool:
    """Set up Comelit platform."""

    coordinator: ComelitBaseCoordinator

    session = await async_client_session(hass)

    if entry.data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        coordinator = ComelitSerialBridge(
            hass,
            entry,
            entry.data[CONF_HOST],
            entry.data.get(CONF_PORT, DEFAULT_PORT),
            entry.data[CONF_PIN],
            session,
        )
        platforms = BRIDGE_PLATFORMS
    else:
        coordinator = ComelitVedoSystem(
            hass,
            entry,
            entry.data[CONF_HOST],
            entry.data.get(CONF_PORT, DEFAULT_PORT),
            entry.data[CONF_PIN],
            session,
        )
        platforms = VEDO_PLATFORMS

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ComelitConfigEntry) -> bool:
    """Unload a config entry."""

    if entry.data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        platforms = BRIDGE_PLATFORMS
    else:
        platforms = VEDO_PLATFORMS

    coordinator = entry.runtime_data
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        await coordinator.api.logout()

    return unload_ok
