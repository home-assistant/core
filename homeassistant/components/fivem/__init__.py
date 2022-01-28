"""The FiveM integration."""
from __future__ import annotations

from datetime import datetime, timedelta

from fivem import FiveM, FiveMServerOfflineError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, MANUFACTURER, SCAN_INTERVAL, SIGNAL_NAME_PREFIX

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FiveM from a config entry."""
    try:
        fivem = FiveMServer(hass, entry.data, entry.entry_id)
        await fivem.initialize()
    except FiveMServerOfflineError as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = fivem

    await fivem.async_update()
    fivem.start_periodic_update()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    fivem: FiveMServer = hass.data[DOMAIN][entry.entry_id]
    fivem.stop_periodic_update()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FiveMServer:
    """Representation of a FiveM server."""

    def __init__(self, hass: HomeAssistant, config_data, unique_id: str) -> None:
        """Initialize server instance."""
        self._hass = hass

        self.unique_id = unique_id
        self.server = None
        self.version = None
        self.gamename: str | None = None

        self.name = config_data[CONF_NAME]
        self.host = config_data[CONF_HOST]
        self.port = config_data[CONF_PORT]
        self.online = False

        self._fivem = FiveM(self.host, self.port)

        self.players_online: int = 0
        self.players_max: int = 0
        self.players_list: list[str] = []
        self.resources_count: int = 0
        self.resources_list: list[str] = []

        # Dispatcher signal name
        self.signal_name = f"{SIGNAL_NAME_PREFIX}_{self.unique_id}"

        # Callback for stopping periodic update.
        self._stop_periodic_update: CALLBACK_TYPE = lambda: None

    async def initialize(self) -> None:
        """Initialize the FiveM server."""
        info = await self._fivem.get_info_raw()
        self.server = info.get("server")
        self.version = info.get("version")
        self.gamename = info.get("vars")["gamename"]

    def start_periodic_update(self) -> None:
        """Start periodic execution of update method."""
        self._stop_periodic_update = async_track_time_interval(
            self._hass, self.async_update, timedelta(seconds=SCAN_INTERVAL)
        )

    def stop_periodic_update(self) -> None:
        """Stop periodic execution of update method."""
        self._stop_periodic_update()

    async def async_update(self, now: datetime = None) -> None:
        """Get server data from 3rd party library and update properties."""
        try:
            server = await self._fivem.get_server()
            self.online = True
        except FiveMServerOfflineError:
            self.online = False

        if self.online:
            self.players_online = len(server.players)
            self.players_max = server.max_players
            self.players_list = []
            for player in server.players:
                self.players_list.append(player.name)
            self.players_list.sort()

            self.resources_count = len(server.resources)
            self.resources_list = server.resources
            self.resources_list.sort()

        async_dispatcher_send(self._hass, self.signal_name)


class FiveMEntity(Entity):
    """Representation of a FiveM base entity."""

    def __init__(
        self, fivem: FiveMServer, type_name: str, icon: str, device_class: str = None
    ) -> None:
        """Initialize base entity."""
        self._fivem = fivem
        self._attr_name = f"{self._fivem.name} {type_name}"
        self._attr_icon = icon
        self._attr_unique_id = f"{self._fivem.unique_id}-{type_name}"
        self._attr_device_class = device_class
        self._attr_should_poll = False

    @property
    def device_info(self):
        """Set the device for the entity."""
        return {
            "identifiers": {(DOMAIN, self._fivem.unique_id)},
            "manufacturer": MANUFACTURER,
            "model": self._fivem.server,
            "name": self._fivem.name,
            "sw_version": self._fivem.version,
        }
