"""The Meraki Dashboard integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MerakiDashboardApi
from .const import (
    CONF_INCLUDED_CLIENTS,
    CONF_TRACK_BLUETOOTH_CLIENTS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_INFRASTRUCTURE_DEVICES,
    DEFAULT_TRACK_BLUETOOTH_CLIENTS,
    DEFAULT_TRACK_CLIENTS,
    DEFAULT_TRACK_INFRASTRUCTURE_DEVICES,
    DOMAIN,
)
from .coordinator import (
    MerakiDashboardConfigEntry,
    MerakiDashboardDataUpdateCoordinator,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
ALL_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]


def _enabled_platforms(entry: ConfigEntry) -> list[Platform]:
    """Determine enabled platforms from config entry options."""
    platforms: list[Platform] = []
    if entry.options.get(
        CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS
    ) or entry.options.get(
        CONF_TRACK_BLUETOOTH_CLIENTS, DEFAULT_TRACK_BLUETOOTH_CLIENTS
    ):
        platforms.append(Platform.DEVICE_TRACKER)
    if entry.options.get(CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS):
        platforms.append(Platform.SENSOR)
    if entry.options.get(
        CONF_TRACK_INFRASTRUCTURE_DEVICES, DEFAULT_TRACK_INFRASTRUCTURE_DEVICES
    ):
        platforms.append(Platform.BINARY_SENSOR)
        platforms.append(Platform.BUTTON)
        if Platform.SENSOR not in platforms:
            platforms.append(Platform.SENSOR)
    return platforms


async def async_setup_entry(
    hass: HomeAssistant, entry: MerakiDashboardConfigEntry
) -> bool:
    """Set up Meraki Dashboard from a config entry."""
    track_clients = entry.options.get(CONF_TRACK_CLIENTS, DEFAULT_TRACK_CLIENTS)
    track_bluetooth_clients = entry.options.get(
        CONF_TRACK_BLUETOOTH_CLIENTS, DEFAULT_TRACK_BLUETOOTH_CLIENTS
    )
    track_infrastructure_devices = entry.options.get(
        CONF_TRACK_INFRASTRUCTURE_DEVICES, DEFAULT_TRACK_INFRASTRUCTURE_DEVICES
    )
    api = MerakiDashboardApi(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    coordinator = MerakiDashboardDataUpdateCoordinator(
        hass,
        entry,
        api,
        track_clients=track_clients,
        track_bluetooth_clients=track_bluetooth_clients,
        track_infrastructure_devices=track_infrastructure_devices,
        included_clients={
            client_mac
            for client_mac in entry.options.get(CONF_INCLUDED_CLIENTS, [])
            if isinstance(client_mac, str)
        },
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    if platforms := _enabled_platforms(entry):
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ALL_PLATFORMS)
