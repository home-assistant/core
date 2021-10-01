"""Support for UpCloud."""
from __future__ import annotations

import dataclasses
from datetime import timedelta
import logging
from typing import Any, Dict

import requests.exceptions
import upcloud_api

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
    STATE_PROBLEM,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

ATTR_CORE_NUMBER = "core_number"
ATTR_HOSTNAME = "hostname"
ATTR_MEMORY_AMOUNT = "memory_amount"
ATTR_TITLE = "title"
ATTR_UUID = "uuid"
ATTR_ZONE = "zone"

CONF_SERVERS = "servers"

DATA_UPCLOUD = "data_upcloud"

DEFAULT_COMPONENT_NAME = "UpCloud {}"
DEFAULT_COMPONENT_DEVICE_CLASS = "power"

CONFIG_ENTRY_DOMAINS = {BINARY_SENSOR_DOMAIN, SWITCH_DOMAIN}

SIGNAL_UPDATE_UPCLOUD = "upcloud_update"

STATE_MAP = {"error": STATE_PROBLEM, "started": STATE_ON, "stopped": STATE_OFF}


class UpCloudDataUpdateCoordinator(
    DataUpdateCoordinator[Dict[str, upcloud_api.Server]]
):
    """UpCloud data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        cloud_manager: upcloud_api.CloudManager,
        update_interval: timedelta,
        username: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass, _LOGGER, name=f"{username}@UpCloud", update_interval=update_interval
        )
        self.cloud_manager = cloud_manager

    async def async_update_config(self, config_entry: ConfigEntry) -> None:
        """Handle config update."""
        self.update_interval = timedelta(
            seconds=config_entry.options[CONF_SCAN_INTERVAL]
        )

    async def _async_update_data(self) -> dict[str, upcloud_api.Server]:
        return {
            x.uuid: x
            for x in await self.hass.async_add_executor_job(
                self.cloud_manager.get_servers
            )
        }


@dataclasses.dataclass
class UpCloudHassData:
    """Home Assistant UpCloud runtime data."""

    coordinators: dict[str, UpCloudDataUpdateCoordinator] = dataclasses.field(
        default_factory=dict
    )


def _config_entry_update_signal_name(config_entry: ConfigEntry) -> str:
    """Get signal name for updates to a config entry."""
    return CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE.format(config_entry.unique_id)


async def _async_signal_options_update(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Signal config entry options update."""
    async_dispatcher_send(
        hass, _config_entry_update_signal_name(config_entry), config_entry
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the UpCloud config entry."""

    manager = upcloud_api.CloudManager(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )

    try:
        await hass.async_add_executor_job(manager.authenticate)
    except upcloud_api.UpCloudAPIError:
        _LOGGER.error("Authentication failed", exc_info=True)
        return False
    except requests.exceptions.RequestException as err:
        _LOGGER.error("Failed to connect", exc_info=True)
        raise ConfigEntryNotReady from err

    if entry.options.get(CONF_SCAN_INTERVAL):
        update_interval = timedelta(seconds=entry.options[CONF_SCAN_INTERVAL])
    else:
        update_interval = DEFAULT_SCAN_INTERVAL

    coordinator = UpCloudDataUpdateCoordinator(
        hass,
        update_interval=update_interval,
        cloud_manager=manager,
        username=entry.data[CONF_USERNAME],
    )

    # Call the UpCloud API to refresh data
    await coordinator.async_config_entry_first_refresh()

    # Listen to config entry updates
    entry.async_on_unload(entry.add_update_listener(_async_signal_options_update))
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            _config_entry_update_signal_name(entry),
            coordinator.async_update_config,
        )
    )

    hass.data[DATA_UPCLOUD] = UpCloudHassData()
    hass.data[DATA_UPCLOUD].coordinators[entry.data[CONF_USERNAME]] = coordinator

    # Forward entry setup
    hass.config_entries.async_setup_platforms(entry, CONFIG_ENTRY_DOMAINS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, CONFIG_ENTRY_DOMAINS
    )

    hass.data[DATA_UPCLOUD].coordinators.pop(config_entry.data[CONF_USERNAME])

    return unload_ok


class UpCloudServerEntity(CoordinatorEntity):
    """Entity class for UpCloud servers."""

    _attr_device_class = DEFAULT_COMPONENT_DEVICE_CLASS

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, upcloud_api.Server]],
        uuid: str,
    ) -> None:
        """Initialize the UpCloud server entity."""
        super().__init__(coordinator)
        self.uuid = uuid

    @property
    def _server(self) -> upcloud_api.Server:
        return self.coordinator.data[self.uuid]

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return self.uuid

    @property
    def name(self) -> str:
        """Return the name of the component."""
        try:
            return DEFAULT_COMPONENT_NAME.format(self._server.title)
        except (AttributeError, KeyError, TypeError):
            return DEFAULT_COMPONENT_NAME.format(self.uuid)

    @property
    def icon(self) -> str:
        """Return the icon of this server."""
        return "mdi:server" if self.is_on else "mdi:server-off"

    @property
    def is_on(self) -> bool:
        """Return true if the server is on."""
        try:
            return STATE_MAP.get(self._server.state, self._server.state) == STATE_ON
        except AttributeError:
            return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and STATE_MAP.get(
            self._server.state, self._server.state
        ) in (STATE_ON, STATE_OFF)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the UpCloud server."""
        return {
            x: getattr(self._server, x, None)
            for x in (
                ATTR_UUID,
                ATTR_TITLE,
                ATTR_HOSTNAME,
                ATTR_ZONE,
                ATTR_CORE_NUMBER,
                ATTR_MEMORY_AMOUNT,
            )
        }
