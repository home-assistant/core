"""Comelit integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PIN,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant

from .const import _LOGGER, DOMAIN
from .coordinator import ComelitSerialBridge

PLATFORMS = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Comelit platform."""
    _LOGGER.debug("Setting up Comelit component")
    coordinator = ComelitSerialBridge(
        entry.data[CONF_HOST],
        entry.data[CONF_PIN],
        hass=hass,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def async_close_connection(event: Event) -> None:
        """Close Comelit connection on HA Stop."""
        await coordinator.api.logout()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    coordinator.async_add_listener(coordinator.async_listener)
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: ComelitSerialBridge = hass.data[DOMAIN][entry.entry_id]
        await coordinator.api.logout()
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
