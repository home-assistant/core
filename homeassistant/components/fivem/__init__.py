"""The FiveM integration."""
from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
import logging
from typing import Any

from fivem import FiveM, FiveMServerOfflineError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_PLAYERS_LIST,
    ATTR_RESOURCES_LIST,
    DOMAIN,
    MANUFACTURER,
    NAME_PLAYERS_MAX,
    NAME_PLAYERS_ONLINE,
    NAME_RESOURCES,
    NAME_STATUS,
    SCAN_INTERVAL,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FiveM from a config entry."""
    _LOGGER.debug(
        "Create FiveM server instance for '%s:%s'",
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )

    try:
        coordinator = FiveMDataUpdateCoordinator(hass, entry.data, entry.entry_id)
        await coordinator.initialize()
    except FiveMServerOfflineError as err:
        raise ConfigEntryNotReady from err

    await coordinator.async_config_entry_first_refresh()
    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    await hass.config_entries.async_reload(entry.entry_id)


class FiveMDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching FiveM data."""

    def __init__(self, hass: HomeAssistant, config_data, unique_id: str) -> None:
        """Initialize server instance."""
        self._hass = hass

        self.unique_id = unique_id
        self.server = None
        self.version = None
        self.gamename: str | None = None

        self.server_name = config_data[CONF_NAME]
        self.host = config_data[CONF_HOST]
        self.port = config_data[CONF_PORT]
        self.online = False

        self._fivem = FiveM(self.host, self.port)

        update_interval = timedelta(seconds=SCAN_INTERVAL)
        _LOGGER.debug("Data will be updated every %s", update_interval)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def initialize(self) -> None:
        """Initialize the FiveM server."""
        info = await self._fivem.get_info_raw()
        self.server = info.get("server")
        self.version = info.get("version")
        self.gamename = info.get("vars")["gamename"]

    async def _async_update_data(self) -> dict[str, Any]:
        """Get server data from 3rd party library and update properties."""
        was_online = self.online

        try:
            server = await self._fivem.get_server()
            self.online = True
        except FiveMServerOfflineError:
            self.online = False

        if was_online and not self.online:
            _LOGGER.warning("Connection to '%s:%s' lost", self.host, self.port)
        elif not was_online and self.online:
            _LOGGER.info("Connection to '%s:%s' (re-)established", self.host, self.port)

        if self.online:
            players_list: list[str] = []
            for player in server.players:
                players_list.append(player.name)
            players_list.sort()

            resources_list = server.resources
            resources_list.sort()

            return {
                NAME_PLAYERS_ONLINE: len(players_list),
                NAME_PLAYERS_MAX: server.max_players,
                NAME_RESOURCES: len(resources_list),
                NAME_STATUS: self.online,
                ATTR_PLAYERS_LIST: players_list,
                ATTR_RESOURCES_LIST: resources_list,
            }

        raise UpdateFailed


class FiveMEntity(CoordinatorEntity):
    """Representation of a FiveM base entity."""

    coordinator: FiveMDataUpdateCoordinator

    def __init__(
        self,
        coordinator: FiveMDataUpdateCoordinator,
        type_name: str,
        icon: str,
        device_class: str = None,
        extra_attrs: list[str] = None,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.type_name = type_name
        self.extra_attrs = extra_attrs

        self._attr_name = f"{self.coordinator.server_name} {type_name}"
        self._attr_unique_id = f"{self.coordinator.unique_id}-{type_name}".lower()
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_should_poll = False
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.coordinator.unique_id)},
            "manufacturer": MANUFACTURER,
            "model": self.coordinator.server,
            "name": self.coordinator.server_name,
            "sw_version": self.coordinator.version,
        }

        self._update_entity()

    def _update_entity(self):
        """Update the entity."""
        self._update_value()

        if self.extra_attrs is not None:
            extras: dict[str, Any] = {}
            for attr in self.extra_attrs:
                extras[attr] = self.coordinator.data[attr]
            self._attr_extra_state_attributes = extras

    @abstractmethod
    def _update_value(self):
        """Update the value of the entity."""
        return NotImplemented

    @callback
    def _handle_coordinator_update(self) -> None:
        """Triggers update of properties after receiving update from coordinator."""
        self._update_entity()
        self.async_write_ha_state()
