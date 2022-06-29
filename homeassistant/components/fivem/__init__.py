"""The FiveM integration."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from fivem import FiveM, FiveMServerOfflineError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
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

    coordinator = FiveMDataUpdateCoordinator(hass, entry.data, entry.entry_id)

    try:
        await coordinator.initialize()
    except FiveMServerOfflineError as err:
        raise ConfigEntryNotReady from err

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FiveMDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching FiveM data."""

    def __init__(
        self, hass: HomeAssistant, config_data: Mapping[str, Any], unique_id: str
    ) -> None:
        """Initialize server instance."""
        self.unique_id = unique_id
        self.server = None
        self.version = None
        self.game_name: str | None = None

        self.host = config_data[CONF_HOST]

        self._fivem = FiveM(self.host, config_data[CONF_PORT])

        update_interval = timedelta(seconds=SCAN_INTERVAL)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def initialize(self) -> None:
        """Initialize the FiveM server."""
        info = await self._fivem.get_info_raw()
        self.server = info["server"]
        self.version = info["version"]
        self.game_name = info["vars"]["gamename"]

    async def _async_update_data(self) -> dict[str, Any]:
        """Get server data from 3rd party library and update properties."""
        try:
            server = await self._fivem.get_server()
        except FiveMServerOfflineError as err:
            raise UpdateFailed from err

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
            NAME_STATUS: self.last_update_success,
            ATTR_PLAYERS_LIST: players_list,
            ATTR_RESOURCES_LIST: resources_list,
        }


@dataclass
class FiveMEntityDescription(EntityDescription):
    """Describes FiveM entity."""

    extra_attrs: list[str] | None = None


class FiveMEntity(CoordinatorEntity[FiveMDataUpdateCoordinator]):
    """Representation of a FiveM base entity."""

    entity_description: FiveMEntityDescription

    def __init__(
        self,
        coordinator: FiveMDataUpdateCoordinator,
        description: FiveMEntityDescription,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_name = f"{self.coordinator.host} {description.name}"
        self._attr_unique_id = f"{self.coordinator.unique_id}-{description.key}".lower()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.unique_id)},
            manufacturer=MANUFACTURER,
            model=self.coordinator.server,
            name=self.coordinator.host,
            sw_version=self.coordinator.version,
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the extra attributes of the sensor."""
        if self.entity_description.extra_attrs is None:
            return None

        return {
            attr: self.coordinator.data[attr]
            for attr in self.entity_description.extra_attrs
        }
