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
        await _migrate_device_identifiers(hass, entry)
        hass.config_entries.async_update_entry(entry=entry, version=4)

    return True


async def _migrate_device_identifiers(
    hass: HomeAssistant, entry: PortainerConfigEntry
) -> None:
    """Migrate device identifiers to include endpoint_id."""
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    for device in devices:
        if device.model != "Container":
            continue

        new_identifiers = _get_migrated_identifiers(
            device, entry.entry_id, device_registry
        )

        if new_identifiers and new_identifiers != device.identifiers:
            device_registry.async_update_device(
                device.id, new_identifiers=new_identifiers
            )


def _get_migrated_identifiers(
    device: dr.DeviceEntry, entry_id: str, device_registry: dr.DeviceRegistry
) -> set[tuple[str, str]] | None:
    """Get new identifiers for a container device."""
    new_identifiers = set()

    for domain, identifier in device.identifiers:
        if domain != DOMAIN:
            new_identifiers.add((domain, identifier))
            continue

        # Check if this is the old format
        parts = identifier.split("_", 1)
        if len(parts) != 2 or parts[0] != entry_id:
            new_identifiers.add((domain, identifier))
            continue

        # Get endpoint_id from via_device
        endpoint_id = _get_endpoint_id_from_via_device(device, device_registry)
        if endpoint_id:
            container_name = parts[1]
            new_identifier = f"{entry_id}_{endpoint_id}_{container_name}"
            new_identifiers.add((domain, new_identifier))
        else:
            # Fallback: Keep old identifier if endpoint not found
            # This can happen if via_device relationship is broken/missing
            new_identifiers.add((domain, identifier))

    return new_identifiers


def _get_endpoint_id_from_via_device(
    device: dr.DeviceEntry, device_registry: dr.DeviceRegistry
) -> str | None:
    """Extract endpoint_id from the via_device relationship."""
    if not device.via_device_id:
        return None

    # Get the endpoint device using the via_device_id
    endpoint_device = device_registry.async_get(device.via_device_id)
    if not endpoint_device:
        return None

    # Extract endpoint_id from the endpoint device's identifiers
    for domain, identifier in endpoint_device.identifiers:
        if domain == DOMAIN:
            parts = identifier.split("_", 1)
            if len(parts) == 2:
                return parts[1]

    return None
