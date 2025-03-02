"""The qbittorrent component."""

import logging
from typing import Any

from qbittorrentapi import APIConnectionError, Forbidden403Error, LoginFailed

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    SERVICE_GET_ALL_TORRENTS,
    SERVICE_GET_TORRENTS,
    STATE_ATTR_ALL_TORRENTS,
    STATE_ATTR_TORRENTS,
    TORRENT_FILTER,
)
from .coordinator import QBittorrentDataCoordinator
from .helpers import format_torrents, setup_client

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

CONF_ENTRY = "entry"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up qBittorrent services."""

    async def handle_get_torrents(service_call: ServiceCall) -> dict[str, Any] | None:
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(service_call.data[ATTR_DEVICE_ID])

        if device_entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_device",
                translation_placeholders={
                    "device_id": service_call.data[ATTR_DEVICE_ID]
                },
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

        coordinator: QBittorrentDataCoordinator = hass.data[DOMAIN][entry_id]
        items = await coordinator.get_torrents(service_call.data[TORRENT_FILTER])
        info = format_torrents(items)
        return {
            STATE_ATTR_TORRENTS: info,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TORRENTS,
        handle_get_torrents,
        supports_response=SupportsResponse.ONLY,
    )

    async def handle_get_all_torrents(
        service_call: ServiceCall,
    ) -> dict[str, Any] | None:
        torrents = {}

        for key, value in hass.data[DOMAIN].items():
            coordinator: QBittorrentDataCoordinator = value
            items = await coordinator.get_torrents(service_call.data[TORRENT_FILTER])
            torrents[key] = format_torrents(items)

        return {
            STATE_ATTR_ALL_TORRENTS: torrents,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ALL_TORRENTS,
        handle_get_all_torrents,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up qBittorrent from a config entry."""

    try:
        client = await hass.async_add_executor_job(
            setup_client,
            config_entry.data[CONF_URL],
            config_entry.data[CONF_USERNAME],
            config_entry.data[CONF_PASSWORD],
            config_entry.data[CONF_VERIFY_SSL],
        )
    except LoginFailed as err:
        raise ConfigEntryNotReady("Invalid credentials") from err
    except Forbidden403Error as err:
        raise ConfigEntryNotReady("Fail to log in, banned user ?") from err
    except APIConnectionError as exc:
        raise ConfigEntryNotReady("Fail to connect to qBittorrent") from exc

    coordinator = QBittorrentDataCoordinator(hass, config_entry, client)

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload qBittorrent config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        del hass.data[DOMAIN][config_entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok
