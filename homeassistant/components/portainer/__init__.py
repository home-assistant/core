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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN
from .coordinator import PortainerCoordinator

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SWITCH]

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
        # Migrate device identifiers from entry_id_container_name to entry_id_endpoint_id_container_name
        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

        for device in devices:
            # Skip endpoint devices (they don't need migration)
            if device.model == "Endpoint":
                continue

            # Migrate container devices
            if device.model == "Container":
                old_identifiers = device.identifiers
                new_identifiers = set()

                for domain, identifier in old_identifiers:
                    if domain == DOMAIN:
                        # Old format: entry_id_container_name
                        # New format: entry_id_endpoint_id_container_name
                        parts = identifier.split("_", 1)
                        if len(parts) == 2 and parts[0] == entry.entry_id:
                            # Extract container name and find endpoint from via_device
                            container_name = parts[1]
                            if device.via_device_id:
                                endpoint_device = device_registry.async_get_device(
                                    identifiers={(DOMAIN, device.via_device_id)}
                                )
                                if endpoint_device:
                                    # Extract endpoint_id from via_device identifier
                                    for via_domain, via_identifier in endpoint_device.identifiers:
                                        if via_domain == DOMAIN:
                                            endpoint_parts = via_identifier.split("_", 1)
                                            if len(endpoint_parts) == 2:
                                                endpoint_id = endpoint_parts[1]
                                                new_identifier = f"{entry.entry_id}_{endpoint_id}_{container_name}"
                                                new_identifiers.add((domain, new_identifier))
                                                break
                    else:
                        new_identifiers.add((domain, identifier))

                if new_identifiers != old_identifiers:
                    device_registry.async_update_device(
                        device.id, new_identifiers=new_identifiers
                    )

        hass.config_entries.async_update_entry(entry=entry, version=4)

    return True
