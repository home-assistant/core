"""The AirLino integration."""

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AirlinoApi
from .const import DEFAULT_API_VERSION, DEFAULT_PORT, is_supported_api_version
from .coordinator import AirlinoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


@dataclass
class AirlinoRuntimeData:
    """Runtime data for the AirLino integration."""

    api: AirlinoApi
    coordinator: AirlinoDataUpdateCoordinator


type AirlinoConfigEntry = ConfigEntry[AirlinoRuntimeData]


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

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AirlinoRuntimeData(api=api, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirlinoConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unloaded:
        await entry.runtime_data.api.async_close()
    return unloaded
