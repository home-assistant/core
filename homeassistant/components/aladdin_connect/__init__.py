"""The Aladdin Connect Genie integration."""

from __future__ import annotations

from genie_partner_sdk.client import AladdinConnectClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import AsyncConfigEntryAuth
from .const import DOMAIN
from .coordinator import AladdinConnectCoordinator

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SENSOR]

type AladdinConnectConfigEntry = ConfigEntry[AladdinConnectCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: AladdinConnectConfigEntry
) -> bool:
    """Set up Aladdin Connect Genie from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    session = OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(async_get_clientsession(hass), session)
    coordinator = AladdinConnectCoordinator(hass, AladdinConnectClient(auth))

    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_remove_stale_devices(hass, entry)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AladdinConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: AladdinConnectConfigEntry
) -> bool:
    """Migrate old config."""
    if config_entry.version < 2:
        config_entry.async_start_reauth(hass)
        hass.config_entries.async_update_entry(
            config_entry,
            version=2,
            minor_version=1,
        )

    return True


def async_remove_stale_devices(
    hass: HomeAssistant, config_entry: AladdinConnectConfigEntry
) -> None:
    """Remove stale devices from device registry."""
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    all_device_ids = {door.unique_id for door in config_entry.runtime_data.doors}

    for device_entry in device_entries:
        device_id: str | None = None

        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_id = identifier[1]
                break

        if device_id is None or device_id not in all_device_ids:
            # If device_id is None an invalid device entry was found for this config entry.
            # If the device_id is not in existing device ids it's a stale device entry.
            # Remove config entry from this device entry in either case.
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=config_entry.entry_id
            )
