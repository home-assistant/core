"""Vodafone Station integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant

from .const import _LOGGER, DOMAIN
from .coordinator import VodafoneStationRouter

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vodafone Station platform."""
    _LOGGER.debug("Setting up Vodafone Station component")
    coordinator = VodafoneStationRouter(
        entry.data[CONF_HOST],
        entry.data[CONF_SSL],
        entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        hass=hass,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def async_close_connection(event: Event) -> None:
        """Close Vodafone connection on HA Stop."""
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
        coordinator: VodafoneStationRouter = hass.data[DOMAIN][entry.entry_id]
        await coordinator.api.logout()
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
