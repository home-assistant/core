"""Services for the qBittorrent integration."""

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    SERVICE_GET_ALL_TORRENTS,
    SERVICE_GET_TORRENTS,
    STATE_ATTR_ALL_TORRENTS,
    STATE_ATTR_TORRENTS,
    TORRENT_FILTER,
)
from .coordinator import QBittorrentConfigEntry, QBittorrentDataCoordinator
from .helpers import format_torrents


async def _handle_get_torrents(service_call: ServiceCall) -> dict[str, Any] | None:
    hass = service_call.hass
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(service_call.data[ATTR_DEVICE_ID])

    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device",
            translation_placeholders={"device_id": service_call.data[ATTR_DEVICE_ID]},
        )

    entry_id = None

    for key, value in device_entry.identifiers:
        if key == DOMAIN:
            entry_id = value
            break
    else:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entry_id",
            translation_placeholders={"device_id": entry_id or ""},
        )

    entry: QBittorrentConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entry_id",
            translation_placeholders={"device_id": entry_id},
        )
    coordinator = entry.runtime_data
    items = await coordinator.get_torrents(service_call.data[TORRENT_FILTER])
    info = format_torrents(items)
    return {
        STATE_ATTR_TORRENTS: info,
    }


async def _handle_get_all_torrents(
    service_call: ServiceCall,
) -> dict[str, Any] | None:
    hass = service_call.hass
    torrents = {}

    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coordinator: QBittorrentDataCoordinator = entry.runtime_data
        items = await coordinator.get_torrents(service_call.data[TORRENT_FILTER])
        torrents[entry.entry_id] = format_torrents(items)

    return {
        STATE_ATTR_ALL_TORRENTS: torrents,
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the qBittorrent integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TORRENTS,
        _handle_get_torrents,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ALL_TORRENTS,
        _handle_get_all_torrents,
        supports_response=SupportsResponse.ONLY,
    )
