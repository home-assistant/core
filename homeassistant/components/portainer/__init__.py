"""The Portainer integration."""

from __future__ import annotations

from pyportainer import Portainer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_URL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import PortainerCoordinator

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]


type PortainerConfigEntry = ConfigEntry[PortainerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Set up Portainer from a config entry."""

    client = Portainer(
        api_url=entry.data[CONF_URL],
        api_key=entry.data[CONF_API_TOKEN],
        session=async_create_clientsession(
            hass=hass, verify_ssl=entry.data[CONF_VERIFY_SSL]
        ),
    )

    coordinator = PortainerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: PortainerConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version < 2:
        data = dict(entry.data)
        data[CONF_URL] = data.pop(CONF_HOST)
        data[CONF_API_TOKEN] = data.pop(CONF_API_KEY)
        hass.config_entries.async_update_entry(entry=entry, data=data, version=2)

    if entry.version < 3:
        data = dict(entry.data)
        data[CONF_VERIFY_SSL] = True
        hass.config_entries.async_update_entry(entry=entry, data=data, version=3)

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    device: DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    coordinator = entry.runtime_data
    valid_identifiers: set[tuple[str, str]] = set()

    # The Portainer integration creates devices for both endpoints and containers. That's why we're doing it double
    valid_identifiers.update(
        (DOMAIN, f"{entry.entry_id}_{endpoint_id}") for endpoint_id in coordinator.data
    )

    valid_identifiers.update(
        (DOMAIN, f"{entry.entry_id}_{container_name}")
        for endpoint in coordinator.data.values()
        for container_name in endpoint.containers
    )

    return not device.identifiers.intersection(valid_identifiers)
