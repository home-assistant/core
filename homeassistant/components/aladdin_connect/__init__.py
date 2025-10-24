"""The Aladdin Connect Genie integration."""

from __future__ import annotations

from genie_partner_sdk.client import AladdinConnectClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    device_registry as dr,
)

from . import api
from .const import CONFIG_FLOW_MINOR_VERSION, CONFIG_FLOW_VERSION, DOMAIN
from .coordinator import AladdinConnectConfigEntry, AladdinConnectCoordinator

PLATFORMS: list[Platform] = [Platform.COVER, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: AladdinConnectConfigEntry
) -> bool:
    """Set up Aladdin Connect Genie from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    client = AladdinConnectClient(
        api.AsyncConfigEntryAuth(aiohttp_client.async_get_clientsession(hass), session)
    )

    doors = await client.get_doors()

    entry.runtime_data = {
        door.unique_id: AladdinConnectCoordinator(hass, entry, client, door)
        for door in doors
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    remove_stale_devices(hass, entry)

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
    if config_entry.version < CONFIG_FLOW_VERSION:
        config_entry.async_start_reauth(hass)
        new_data = {**config_entry.data}
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            version=CONFIG_FLOW_VERSION,
            minor_version=CONFIG_FLOW_MINOR_VERSION,
        )

    return True


def remove_stale_devices(
    hass: HomeAssistant,
    config_entry: AladdinConnectConfigEntry,
) -> None:
    """Remove stale devices from device registry."""
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    all_device_ids = set(config_entry.runtime_data)

    for device_entry in device_entries:
        device_id: str | None = None
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                device_id = identifier[1]
                break

        if device_id and device_id not in all_device_ids:
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=config_entry.entry_id
            )
