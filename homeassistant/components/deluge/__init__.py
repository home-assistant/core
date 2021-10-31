"""The Deluge integration."""
from __future__ import annotations

import logging
import socket
from ssl import SSLError

from deluge_client.client import DelugeRPCClient, FailedToReconnectException

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_WEB_PORT,
    DATA_KEY_API,
    DATA_KEY_COORDINATOR,
    DEFAULT_NAME,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)

PLATFORMS = [SENSOR_DOMAIN, SWITCH_DOMAIN]

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
    except (ConnectionRefusedError, socket.timeout, SSLError) as ex:
        raise ConfigEntryNotReady("Connection to Deluge Daemon failed") from ex
    except Exception as ex:  # pylint:disable=broad-except
        if type(ex).__name__ == "BadLoginError":
            raise ConfigEntryAuthFailed(
                "Credentials for Deluge client are not valid"
            ) from ex
        _LOGGER.error("Unknown error connecting to Deluge: %s", ex)

    async def async_update_data() -> dict[str, dict[str, int | str]]:
        """Get the latest data from Deluge and updates the state."""
        data = {}
        try:
            data[SENSOR_DOMAIN] = await hass.async_add_executor_job(
                api.call,
                "core.get_session_status",
                [
                    "upload_rate",
                    "download_rate",
                    "dht_upload_rate",
                    "dht_download_rate",
                ],
            )
            data[SWITCH_DOMAIN] = await hass.async_add_executor_job(
                api.call, "core.get_torrents_status", {}, ["paused"]
            )
        except (
            ConnectionRefusedError,
            socket.timeout,
            SSLError,
            FailedToReconnectException,
        ) as ex:
            raise UpdateFailed(f"Connection to Deluge Daemon Lost: {ex}") from ex
        except Exception as ex:  # pylint:disable=broad-except
            if type(ex).__name__ == "BadLoginError":
                raise ConfigEntryAuthFailed(
                    "Credentials for Deluge client are not valid"
                ) from ex
            _LOGGER.error("Unknown error connecting to Deluge: %s", ex)

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=entry.title,
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_UPDATES,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_API: api,
        DATA_KEY_COORDINATOR: coordinator,
    }
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class DelugeEntity(CoordinatorEntity):
    """Representation of a Deluge entity."""

    def __init__(
        self,
        api: DelugeRPCClient,
        coordinator: DataUpdateCoordinator,
        server_unique_id: str,
    ) -> None:
        """Initialize a Deluge entity."""
        super().__init__(coordinator)
        self.api = api
        self._server_unique_id = server_unique_id
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{api.host}:{api.web_port}",
            entry_type="service",
            identifiers={(DOMAIN, server_unique_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
            sw_version=api.deluge_version,
        )
