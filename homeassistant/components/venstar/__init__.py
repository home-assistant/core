"""The venstar component."""

from __future__ import annotations

from venstarcolortouch import VenstarColorTouch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VENSTAR_TIMEOUT
from .coordinator import VenstarDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Set up the Venstar thermostat."""
    username = config.data.get(CONF_USERNAME)
    password = config.data.get(CONF_PASSWORD)
    pin = config.data.get(CONF_PIN)
    host = config.data[CONF_HOST]
    timeout = VENSTAR_TIMEOUT
    protocol = "https" if config.data[CONF_SSL] else "http"

    client = VenstarColorTouch(
        addr=host,
        timeout=timeout,
        user=username,
        password=password,
        pin=pin,
        proto=protocol,
    )

    venstar_data_coordinator = VenstarDataUpdateCoordinator(
        hass,
        venstar_connection=client,
    )
    await venstar_data_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config.entry_id] = venstar_data_coordinator
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Unload the config and platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(config, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config.entry_id)
    return unload_ok
