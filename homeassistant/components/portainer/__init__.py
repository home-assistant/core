"""The Portainer integration."""

from __future__ import annotations

import logging

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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN
from .coordinator import PortainerCoordinator

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SWITCH]
_LOGGER = logging.getLogger(__name__)

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

    if entry.version < 4:
        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

        for device in devices:
            if device.via_device_id is None:
                continue

            parent_device = device_registry.async_get(device.via_device_id)
            parent_identifier = next(iter(parent_device.identifiers))
            endpoint_id = parent_identifier[1].split("_")[-1]

            for domain, identifier in device.identifiers:
                container_name = identifier.split("_", 1)[1]
                new_identifier = (DOMAIN, f"{entry.entry_id}_{endpoint_id}_{container_name}")
                device_registry.async_update_device(
                    device.id, new_identifiers={new_identifier}
                )

        hass.config_entries.async_update_entry(entry=entry, version=4)
            device_registry.async_update_device(
                device.id, new_identifiers=new_identifiers
            )

        hass.config_entries.async_update_entry(entry=entry, version=4)

    return True
