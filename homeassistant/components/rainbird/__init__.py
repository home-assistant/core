"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

from pyrainbird.async_client import AsyncRainbirdClient, AsyncRainbirdController
from pyrainbird.exceptions import RainbirdApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SERIAL_NUMBER
from .coordinator import RainbirdData, RainbirdUpdateCoordinator

PLATFORMS = [
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.CALENDAR,
]


DOMAIN = "rainbird"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the config entry for Rain Bird."""

    hass.data.setdefault(DOMAIN, {})

    controller = AsyncRainbirdController(
        AsyncRainbirdClient(
            async_get_clientsession(hass),
            entry.data[CONF_HOST],
            entry.data[CONF_PASSWORD],
        )
    )
    try:
        model_info = await controller.get_model_and_version()
    except RainbirdApiException as err:
        raise ConfigEntryNotReady from err
    coordinator = RainbirdUpdateCoordinator(
        hass,
        name=entry.title,
        controller=controller,
        serial_number=entry.data[CONF_SERIAL_NUMBER],
        model_info=model_info,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.data[DOMAIN][entry.entry_id] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
