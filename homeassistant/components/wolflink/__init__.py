"""The Wolf SmartSet Service integration."""

import asyncio
import logging

from httpx import RequestError
from wolf_comm.models import Device
from wolf_comm.wolf_client import FetchFailed, WolfClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.httpx_client import create_async_httpx_client
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import DOMAIN, MANUFACTURER
from .coordinator import WolflinkConfigEntry, WolfLinkCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WolflinkConfigEntry) -> bool:
    """Set up Wolf SmartSet Service from a config entry."""
    wolf_client = WolfClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        client=create_async_httpx_client(hass=hass, verify_ssl=False, timeout=20),
    )

    try:
        devices = await wolf_client.fetch_system_list()
    except (FetchFailed, RequestError) as exception:
        raise ConfigEntryNotReady(
            f"Error communicating with API: {exception}"
        ) from exception

    device_registry = dr.async_get(hass)

    async def _async_setup_device(
        device: Device,
    ) -> tuple[int, WolfLinkCoordinator] | None:
        """Initialize a coordinator for a device, or skip if it can't be set up."""
        coordinator = WolfLinkCoordinator(hass, entry, wolf_client, device)
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            _LOGGER.warning(
                "Skipping device %s (%s): could not fetch parameters",
                device.name,
                device.id,
            )
            return None
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, str(device.id))},
            configuration_url="https://www.wolf-smartset.com/",
            manufacturer=MANUFACTURER,
            name=device.name,
        )
        return device.id, coordinator

    results = await asyncio.gather(*(_async_setup_device(device) for device in devices))
    entry.runtime_data = dict(filter(None, results))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WolflinkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry.

    v1.1 → v1.2: convert unique_id from int to string.
    v1   → v2.2: convert from device-oriented entry to a hub entry keyed
                 by username; merge sibling entries for the same account.
    """
    if entry.version == 1:
        if entry.minor_version == 1 and isinstance(entry.unique_id, int):
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

        _migrate_v1_to_v2(hass, entry)

    return True


def _migrate_v1_to_v2(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate a v1 device-oriented entry to v2.2 hub.

    Multiple v1 entries for the same account are merged into a single hub
    entry — devices and entities are reattached to the surviving entry first,
    then the duplicate entry is scheduled for removal.
    """
    username = entry.data[CONF_USERNAME]
    target_unique_id = username.lower()
    raw_device_id = entry.data["device_id"]
    if isinstance(raw_device_id, list):
        if not raw_device_id:
            return
        raw_device_id = raw_device_id[0]
    legacy_device_id = int(raw_device_id)

    sibling = next(
        (
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id and e.unique_id == target_unique_id
        ),
        None,
    )
    if sibling is not None:
        # An entry for this account already migrated — reattach our device
        # to it, then schedule ourselves for removal. We can't await the
        # removal here because we're inside async_migrate_entry; the entry
        # is still mid-setup and async_remove waits for setup to finish.
        _reattach_device_to_hub(hass, sibling, entry, legacy_device_id)
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return

    hass.config_entries.async_update_entry(
        entry,
        data={
            CONF_USERNAME: username,
            CONF_PASSWORD: entry.data[CONF_PASSWORD],
        },
        unique_id=target_unique_id,
        version=2,
        minor_version=2,
    )
    _reattach_device_to_hub(hass, entry, entry, legacy_device_id)


def _reattach_device_to_hub(
    hass: HomeAssistant,
    hub_entry: ConfigEntry,
    source_entry: ConfigEntry,
    device_id: int,
) -> None:
    """Move device and entity registry rows from source_entry to hub_entry.

    Called during migration when a v1 device-oriented entry is being merged
    into the hub entry. Handles the disabled_by flag so disabled state
    survives the move.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, str(device_id))})
    if device is None:
        return

    # The device registry will set the disabled_by flag to None when moving a
    # device disabled by CONFIG_ENTRY to an enabled config entry, but we want
    # to set it to USER instead.
    device_disabled_by: dr.DeviceEntryDisabler | UndefinedType = UNDEFINED
    if (
        device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
        and hub_entry.disabled_by is None
    ):
        device_disabled_by = dr.DeviceEntryDisabler.USER

    device_registry.async_update_device(
        device.id,
        disabled_by=device_disabled_by,
        new_config_entry_id=hub_entry.entry_id,
    )

    for entity_entry in er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    ):
        if entity_entry.config_entry_id != source_entry.entry_id:
            continue
        entity_disabled_by = entity_entry.disabled_by
        if entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY:
            entity_disabled_by = er.RegistryEntryDisabler.DEVICE
        entity_registry.async_update_entity(
            entity_entry.entity_id,
            config_entry_id=hub_entry.entry_id,
            disabled_by=entity_disabled_by,
        )
