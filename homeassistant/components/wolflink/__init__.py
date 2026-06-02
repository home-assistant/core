"""The Wolf SmartSet Service integration."""

import asyncio
import logging
from types import MappingProxyType

from httpx import RequestError
from wolf_comm.models import Device
from wolf_comm.wolf_client import FetchFailed, WolfClient

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.httpx_client import create_async_httpx_client

from .const import DEVICE_ID, DOMAIN, SUBENTRY_TYPE_DEVICE
from .coordinator import WolflinkConfigEntry, WolfLinkCoordinator, fetch_parameters

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

    devices_by_id: dict[int, Device] = {device.id: device for device in devices}

    async def _async_setup_subentry(
        subentry: ConfigSubentry,
    ) -> tuple[str, WolfLinkCoordinator] | None:
        """Initialize a coordinator for a subentry, or skip if device is gone."""
        device_id: int = subentry.data[DEVICE_ID]
        device = devices_by_id.get(device_id)
        if device is None:
            return None
        try:
            parameters = await _fetch_parameters_init(
                wolf_client, device.gateway, device.id
            )
            coordinator = WolfLinkCoordinator(
                hass, entry, subentry, wolf_client, parameters, device.gateway
            )
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            _LOGGER.warning(
                "Skipping device %s (%s): could not fetch parameters",
                subentry.title,
                device_id,
            )
            return None
        return subentry.subentry_id, coordinator

    results = await asyncio.gather(
        *(
            _async_setup_subentry(subentry)
            for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE)
        )
    )
    entry.runtime_data = dict(filter(None, results))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WolflinkConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version > 2 or (entry.version == 2 and entry.minor_version > 2):
        return False

    if entry.version == 1:
        # v1.1 → v1.2: convert unique_id from int to string.
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

        # v1 → v2.2: convert from device-oriented entry to a hub entry with
        # one subentry per device.
        _migrate_v1_to_v2_2(hass, entry)
        return True

    if entry.version == 2 and entry.minor_version == 1:
        # v2.1 → v2.2: convert hub entry's DEVICE_ID list to device subentries.
        _migrate_v2_1_to_v2_2(hass, entry)

    return True


def _migrate_v1_to_v2_2(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate a v1 device-oriented entry to v2.2 hub-with-subentries.

    Multiple v1 entries for the same account are merged into a single hub
    entry — each device becomes a subentry on the surviving entry.
    """
    username = entry.data[CONF_USERNAME]
    target_unique_id = username.lower()

    # Normalize the legacy device id into list[int]. v1 entries stored a
    # scalar (int in v1.1, str in v1.2 after the int→str migration), but
    # tolerate a list shape too in case of partial or manual edits.
    old_device_id = entry.data.get(DEVICE_ID)
    new_ids: list[int] = []
    if isinstance(old_device_id, list):
        new_ids = [int(did) for did in old_device_id if did is not None]
    elif old_device_id is not None:
        new_ids = [int(old_device_id)]

    sibling = next(
        (
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id and e.unique_id == target_unique_id
        ),
        None,
    )
    if sibling is not None:
        # An entry for this account already migrated — merge our devices into
        # it as subentries and drop ourselves.
        for device_id in new_ids:
            _add_device_subentry(hass, sibling, device_id, source_entry=entry)
        hass.config_entries.async_update_entry(entry, version=2, minor_version=2)
        hass.async_create_task(hass.config_entries.async_reload(sibling.entry_id))
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
    for device_id in new_ids:
        _add_device_subentry(hass, entry, device_id, source_entry=entry)


def _migrate_v2_1_to_v2_2(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate a v2.1 hub entry (DEVICE_ID list in data) to v2.2 subentries."""
    device_ids = [int(d) for d in entry.data.get(DEVICE_ID, []) if d is not None]
    new_data = {k: v for k, v in entry.data.items() if k != DEVICE_ID}
    hass.config_entries.async_update_entry(
        entry, data=new_data, version=2, minor_version=2
    )
    for device_id in device_ids:
        _add_device_subentry(hass, entry, device_id, source_entry=entry)


def _add_device_subentry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_id: int,
    *,
    source_entry: ConfigEntry,
) -> None:
    """Create a device subentry and reattach the matching device + entities.

    ``source_entry`` is the entry the device/entity registry rows are currently
    attached to (it can differ from ``entry`` during a sibling-merge).
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, str(device_id))})
    title = device.name if device and device.name else f"Wolf {device_id}"

    subentry = ConfigSubentry(
        data=MappingProxyType({DEVICE_ID: device_id}),
        subentry_type=SUBENTRY_TYPE_DEVICE,
        title=title,
        unique_id=str(device_id),
    )
    hass.config_entries.async_add_subentry(entry, subentry)

    if device is None:
        return

    # Device and entity registries don't update the disabled_by flag when
    # moving a row from one config entry to another, so we do it manually so
    # disabled state survives the move.
    device_disabled_by = device.disabled_by
    if device_disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY:
        device_disabled_by = dr.DeviceEntryDisabler.USER

    # Order matters: attach the new subentry to the device first, then move
    # the entities, then drop the bare (entry, None) attachment. The device-
    # registry's entity-cleanup handler removes any entity whose
    # (config_entry_id, config_subentry_id) is no longer on the device — so we
    # must move entities to (entry, subentry) before removing (entry, None).
    device_registry.async_update_device(
        device.id,
        disabled_by=device_disabled_by,
        add_config_subentry_id=subentry.subentry_id,
        add_config_entry_id=entry.entry_id,
    )

    for entity_entry in er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    ):
        entity_disabled_by = entity_entry.disabled_by
        if entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY:
            entity_disabled_by = er.RegistryEntryDisabler.DEVICE
        entity_registry.async_update_entity(
            entity_entry.entity_id,
            config_entry_id=entry.entry_id,
            config_subentry_id=subentry.subentry_id,
            disabled_by=entity_disabled_by,
        )

    if source_entry.entry_id != entry.entry_id:
        device_registry.async_update_device(
            device.id, remove_config_entry_id=source_entry.entry_id
        )
    else:
        device_registry.async_update_device(
            device.id,
            remove_config_entry_id=entry.entry_id,
            remove_config_subentry_id=None,
        )


async def _fetch_parameters_init(client: WolfClient, gateway_id: int, device_id: int):
    """Fetch all available parameters, raising ConfigEntryNotReady on failure."""
    try:
        return await fetch_parameters(client, gateway_id, device_id)
    except (FetchFailed, RequestError) as exception:
        raise ConfigEntryNotReady(
            f"Error communicating with API: {exception}"
        ) from exception
