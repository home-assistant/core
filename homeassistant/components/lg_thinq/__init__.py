"""Support for LG ThinQ Connect device."""

from __future__ import annotations

import asyncio
import logging

from thinqconnect import ThinQApi, ThinQAPIException
from thinqconnect.integration import async_get_ha_bridge_list

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CONNECT_CLIENT_ID
from .coordinator import DeviceDataUpdateCoordinator, async_setup_device_coordinator

type ThinqConfigEntry = ConfigEntry[dict[str, DeviceDataUpdateCoordinator]]

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Set up an entry."""
    entry.runtime_data = {}

    access_token = entry.data[CONF_ACCESS_TOKEN]
    client_id = entry.data[CONF_CONNECT_CLIENT_ID]
    country_code = entry.data[CONF_COUNTRY]

    thinq_api = ThinQApi(
        session=async_get_clientsession(hass),
        access_token=access_token,
        country_code=country_code,
        client_id=client_id,
    )

    # Setup coordinators and register devices.
    await async_setup_coordinators(hass, entry, thinq_api)

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean up devices they are no longer in use.
    async_cleanup_device_registry(hass, entry)

    return True


async def async_setup_coordinators(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    thinq_api: ThinQApi,
) -> None:
    """Set up coordinators and register devices."""
    # Get a list of ha bridge.
    try:
        bridge_list = await async_get_ha_bridge_list(thinq_api)
    except ThinQAPIException as exc:
        raise ConfigEntryNotReady(exc.message) from exc

    if not bridge_list:
        return

    # Setup coordinator per device.
    task_list = [
        hass.async_create_task(async_setup_device_coordinator(hass, bridge))
        for bridge in bridge_list
    ]
    task_result = await asyncio.gather(*task_list)
    for coordinator in task_result:
        entry.runtime_data[coordinator.unique_id] = coordinator


@callback
def async_cleanup_device_registry(hass: HomeAssistant, entry: ThinqConfigEntry) -> None:
    """Clean up device registry."""
    new_device_unique_ids = [
        coordinator.unique_id for coordinator in entry.runtime_data.values()
    ]
    device_registry = dr.async_get(hass)
    existing_entries = dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    )

    # Remove devices that are no longer exist.
    for old_entry in existing_entries:
        old_unique_id = next(iter(old_entry.identifiers))[1]
        if old_unique_id not in new_device_unique_ids:
            device_registry.async_remove_device(old_entry.id)
            _LOGGER.debug("Remove device_registry: device_id=%s", old_entry.id)


async def async_unload_entry(hass: HomeAssistant, entry: ThinqConfigEntry) -> bool:
    """Unload the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
