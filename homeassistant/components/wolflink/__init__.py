"""The Wolf SmartSet Service integration."""

import logging

from httpx import RequestError
from wolf_comm.wolf_client import FetchFailed, WolfClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import create_async_httpx_client

from .const import CONF_DEVICES, DOMAIN
from .coordinator import WolfLinkCoordinator, WolfLinkData, fetch_parameters

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
            f"Error fetching system list: {exception}"
        ) from exception

    # Default to all devices if options not yet set (e.g. during migration)
    selected_ids = set(entry.options.get(CONF_DEVICES, [str(d.id) for d in devices]))

    coordinators: list[WolfLinkCoordinator] = []
    for device in devices:
        if str(device.id) not in selected_ids:
            continue
        _LOGGER.debug(
            "Setting up wolflink device: %s (ID: %s, gateway: %s)",
            device.name,
            device.id,
            device.gateway,
        )
        parameters = await fetch_parameters_init(wolf_client, device.gateway, device.id)
        coordinator = WolfLinkCoordinator(
            hass,
            entry,
            wolf_client,
            parameters,
            device.gateway,
            device.id,
            device.name,
        )
        await coordinator.async_refresh()
        coordinators.append(coordinator)

    entry.runtime_data = WolfLinkData(
        wolf_client=wolf_client, coordinators=coordinators
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version == 1:
        # Step 1: if minor_version == 1, convert integer unique_id and device registry identifiers to strings
        if entry.minor_version == 1:
            if isinstance(entry.unique_id, int):
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

        # Step 2: migrate version 1.x → 2.1 (strip device keys, set username unique_id)
        new_unique_id = entry.data[CONF_USERNAME].lower()
        existing = hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, new_unique_id
        )
        if existing is not None and existing.entry_id != entry.entry_id:
            # A migrated entry for this account already exists; remove this duplicate
            _LOGGER.warning(
                "Removing duplicate wolflink entry for account %s (entry %s)",
                new_unique_id,
                entry.entry_id,
            )
            return False

        new_data = {
            CONF_USERNAME: entry.data[CONF_USERNAME],
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
        }
        hass.config_entries.async_update_entry(
            entry,
            unique_id=new_unique_id,
            data=new_data,
            version=2,
            minor_version=1,
        )

    return True


async def fetch_parameters_init(
    client: WolfClient,
    gateway_id: int,
    device_id: int,
):
    """Fetch all available parameters with usage of WolfClient but handles all exceptions and results in ConfigEntryNotReady."""
    try:
        return await fetch_parameters(client, gateway_id, device_id)
    except (FetchFailed, RequestError) as exception:
        raise ConfigEntryNotReady(
            f"Error communicating with API: {exception}"
        ) from exception
