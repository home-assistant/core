"""The Wolf SmartSet Service integration."""

import asyncio

from httpx import RequestError
from wolf_comm.models import Device
from wolf_comm.wolf_client import FetchFailed, WolfClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import create_async_httpx_client

from .const import DEVICE_ID, DOMAIN, MANUFACTURER
from .coordinator import (
    WolflinkConfigEntry,
    WolfLinkCoordinator,
    WolflinkData,
    fetch_parameters,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WolflinkConfigEntry) -> bool:
    """Set up Wolf SmartSet Service from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    wolf_client = WolfClient(
        username,
        password,
        client=create_async_httpx_client(hass=hass, verify_ssl=False, timeout=20),
    )

    try:
        devices = await wolf_client.fetch_system_list()
    except (FetchFailed, RequestError) as exception:
        raise ConfigEntryNotReady(
            f"Error communicating with API: {exception}"
        ) from exception

    if not devices:
        raise ConfigEntryNotReady("No devices found on this account")

    selected_ids: list[int] | None = entry.data.get(DEVICE_ID)
    if selected_ids:
        devices = [d for d in devices if d.id in selected_ids]

    device_registry = dr.async_get(hass)

    async def _async_setup_device(device: Device) -> WolfLinkCoordinator:
        """Initialize a coordinator and register the device."""
        parameters = await _fetch_parameters_init(
            wolf_client, device.gateway, device.id
        )
        coordinator = WolfLinkCoordinator(
            hass,
            entry,
            wolf_client,
            parameters,
            device.gateway,
            device.id,
            device.name,
        )
        await coordinator.async_config_entry_first_refresh()
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, str(device.id))},
            configuration_url="https://www.wolf-smartset.com/",
            manufacturer=MANUFACTURER,
            name=device.name,
        )
        return coordinator

    coordinators = list(
        await asyncio.gather(*(_async_setup_device(device) for device in devices))
    )

    entry.runtime_data = WolflinkData(client=wolf_client, coordinators=coordinators)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WolflinkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version > 2:
        return False

    if entry.version == 1:
        # v1.1 → v1.2: convert unique_id from int to string
        if entry.minor_version == 1:
            if isinstance(entry.unique_id, int):
                hass.config_entries.async_update_entry(
                    entry, unique_id=str(entry.unique_id)
                )
                device_registry = dr.async_get(hass)
                for device in dr.async_entries_for_config_entry(
                    device_registry, entry.entry_id
                ):
                    new_identifiers = {
                        (DOMAIN, str(identifier[1]))
                        if identifier[0] == DOMAIN
                        else identifier
                        for identifier in device.identifiers
                    }
                    device_registry.async_update_device(
                        device.id, new_identifiers=new_identifiers
                    )

        # v1 → v2: convert from device-oriented to hub-oriented
        username = entry.data[CONF_USERNAME]
        target_unique_id = username.lower()
        old_device_id = entry.data.get(DEVICE_ID)
        new_id = int(old_device_id) if old_device_id else None

        # If a sibling entry for the same account already exists (either
        # already migrated, or migrated earlier in this startup), merge into
        # it and drop the current entry instead of creating a duplicate.
        sibling = next(
            (
                e
                for e in hass.config_entries.async_entries(DOMAIN)
                if e.entry_id != entry.entry_id and e.unique_id == target_unique_id
            ),
            None,
        )
        if sibling is not None:
            existing_ids: list[int] = sibling.data.get(DEVICE_ID, [])
            merged_ids = list(
                dict.fromkeys(
                    [*existing_ids, new_id] if new_id is not None else existing_ids
                )
            )
            hass.config_entries.async_update_entry(
                sibling,
                data={**sibling.data, DEVICE_ID: merged_ids},
            )
            # Mark this duplicate as migrated so HA doesn't retry, then remove it.
            hass.config_entries.async_update_entry(entry, version=2, minor_version=1)
            hass.async_create_task(hass.config_entries.async_reload(sibling.entry_id))
            hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
            return True

        new_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
            DEVICE_ID: [new_id] if new_id is not None else [],
        }
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            unique_id=target_unique_id,
            version=2,
            minor_version=1,
        )

    return True


async def _fetch_parameters_init(client: WolfClient, gateway_id: int, device_id: int):
    """Fetch all available parameters, raising ConfigEntryNotReady on failure."""
    try:
        return await fetch_parameters(client, gateway_id, device_id)
    except (FetchFailed, RequestError) as exception:
        raise ConfigEntryNotReady(
            f"Error communicating with API: {exception}"
        ) from exception
