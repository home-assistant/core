"""The AirLino integration."""

import asyncio
from dataclasses import dataclass, field
import logging

from airlino_api import DEFAULT_API_VERSION, DEFAULT_PORT, AirlinoApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SETUP_VERIFIED, DOMAIN, is_supported_api_version
from .coordinator import AirlinoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


@dataclass
class AirlinoRuntimeData:
    """Runtime data for the AirLino integration."""

    api: AirlinoApi
    coordinator: AirlinoDataUpdateCoordinator
    group_mutation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


type AirlinoConfigEntry = ConfigEntry[AirlinoRuntimeData]


def _group_mutation_lock(hass: HomeAssistant) -> asyncio.Lock:
    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime_data = getattr(entry, "runtime_data", None)
        if isinstance(runtime_data, AirlinoRuntimeData):
            return runtime_data.group_mutation_lock
    return asyncio.Lock()


async def async_setup_entry(hass: HomeAssistant, entry: AirlinoConfigEntry) -> bool:
    """Set up AirLino from a config entry."""

    api_version = entry.data.get("api_version", DEFAULT_API_VERSION)
    if not is_supported_api_version(api_version):
        _LOGGER.error(
            "Cannot set up AirLino with unsupported API version %s", api_version
        )
        return False

    api = AirlinoApi(
        host=entry.data["host"],
        port=entry.data.get("port", DEFAULT_PORT),
        api_version=api_version,
        session=async_get_clientsession(hass),
    )

    coordinator = AirlinoDataUpdateCoordinator(hass, entry, api)
    entry.runtime_data = AirlinoRuntimeData(
        api=api,
        coordinator=coordinator,
        group_mutation_lock=_group_mutation_lock(hass),
    )

    await coordinator.async_config_entry_first_refresh()

    if not entry.data.get(CONF_SETUP_VERIFIED, False):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_SETUP_VERIFIED: True}
        )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirlinoConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unloaded:
        await entry.runtime_data.api.async_close()
    return unloaded
