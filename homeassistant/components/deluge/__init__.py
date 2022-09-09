"""The Deluge integration."""
from __future__ import annotations

import logging
import socket
from ssl import SSLError

from deluge_client.client import DelugeRPCClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_WEB_PORT, DEFAULT_NAME, DOMAIN
from .coordinator import DelugeDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Deluge from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    api = await hass.async_add_executor_job(
        DelugeRPCClient, host, port, username, password
    )
    api.web_port = entry.data[CONF_WEB_PORT]
    try:
        await hass.async_add_executor_job(api.connect)
    except (
        ConnectionRefusedError,
        socket.timeout,
        SSLError,
    ) as ex:
        raise ConfigEntryNotReady("Connection to Deluge Daemon failed") from ex
    except Exception as ex:  # pylint:disable=broad-except
        if type(ex).__name__ == "BadLoginError":
            raise ConfigEntryAuthFailed(
                "Credentials for Deluge client are not valid"
            ) from ex
        _LOGGER.error("Unknown error connecting to Deluge: %s", ex)

    coordinator = DelugeDataUpdateCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class DelugeEntity(CoordinatorEntity[DelugeDataUpdateCoordinator]):
    """Representation of a Deluge entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DelugeDataUpdateCoordinator) -> None:
        """Initialize a Deluge entity."""
        super().__init__(coordinator)
        self._server_unique_id = coordinator.config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{coordinator.api.host}:{coordinator.api.web_port}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
            sw_version=coordinator.api.deluge_version,
        )
