"""The Husqvarna Automower integration."""

import logging

from aioautomower.session import AutomowerSession
from aiohttp import ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util

from . import api
from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.DEVICE_TRACKER,
    Platform.LAWN_MOWER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type AutomowerConfigEntry = ConfigEntry[AutomowerDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AutomowerConfigEntry) -> bool:
    """Set up this integration using UI."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    api_api = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass),
        session,
    )
    time_zone_str = str(dt_util.DEFAULT_TIME_ZONE)
    automower_api = AutomowerSession(
        api_api,
        await dt_util.async_get_time_zone(time_zone_str),
    )
    try:
        await api_api.async_get_access_token()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err

    if "amc:api" not in entry.data["token"]["scope"]:
        # We raise ConfigEntryAuthFailed here because the websocket can't be used
        # without the scope. So only polling would be possible.
        raise ConfigEntryAuthFailed

    coordinator = AutomowerDataUpdateCoordinator(hass, automower_api)
    await coordinator.async_config_entry_first_refresh()
    available_devices = list(coordinator.data)
    cleanup_removed_devices(hass, coordinator.config_entry, available_devices)
    entry.runtime_data = coordinator

    entry.async_create_background_task(
        hass,
        coordinator.client_listen(hass, entry, automower_api),
        "websocket_task",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AutomowerConfigEntry) -> bool:
    """Handle unload of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def cleanup_removed_devices(
    hass: HomeAssistant,
    config_entry: AutomowerConfigEntry,
    available_devices: list[str],
) -> None:
    """Cleanup entity and device registry from removed devices."""
    device_reg = dr.async_get(hass)
    identifiers = {(DOMAIN, mower_id) for mower_id in available_devices}
    for device in dr.async_entries_for_config_entry(device_reg, config_entry.entry_id):
        if not set(device.identifiers) & identifiers:
            _LOGGER.debug("Removing obsolete device entry %s", device.name)
            device_reg.async_update_device(
                device.id, remove_config_entry_id=config_entry.entry_id
            )


def remove_work_area_entities(
    hass: HomeAssistant,
    config_entry: AutomowerConfigEntry,
    removed_work_areas: set[int],
    mower_id: str,
) -> None:
    """Remove all unused work area entities for the specified mower."""
    entity_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_reg, config_entry.entry_id
    ):
        for work_area_id in removed_work_areas:
            if entity_entry.unique_id.startswith(f"{mower_id}_{work_area_id}_"):
                _LOGGER.info("Deleting: %s", entity_entry.entity_id)
                entity_reg.async_remove(entity_entry.entity_id)
