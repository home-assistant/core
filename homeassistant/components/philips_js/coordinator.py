"""Coordinator for the Philips TV integration."""

import asyncio
from datetime import timedelta
import logging
from typing import TypedDict, override

from haphilipsjs import (
    AutenticationFailure,
    ConnectionFailure,
    GeneralFailure,
    PhilipsTV,
)
from haphilipsjs.typing import (
    MenuItemsSettingsCurrentValueValue,
    MenuItemsSettingsNode,
    SystemType,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ALLOW_NOTIFY, CONF_MENU_NODES, CONF_SYSTEM, DOMAIN, TV_STATE_ON
from .helpers import get_node_strings

_LOGGER = logging.getLogger(__name__)


class EntitySetupData(TypedDict):
    """Description of a menu node selected to be exposed as an entity."""

    node: MenuItemsSettingsNode
    name: str


type PhilipsTVConfigEntry = ConfigEntry[PhilipsTVDataUpdateCoordinator]


class PhilipsTVDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to update data."""

    config_entry: PhilipsTVConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PhilipsTVConfigEntry,
        api: PhilipsTV,
    ) -> None:
        """Set up the coordinator."""
        self.api = api
        self._notify_future: asyncio.Task | None = None
        self.settings: dict[int, MenuItemsSettingsCurrentValueValue | None] = {}
        self.settings_nodes: list[EntitySetupData] = config_entry.options.get(
            CONF_MENU_NODES, []
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=2.0, immediate=False
            ),
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
            },
            manufacturer="Philips",
            model=self.system.get("model"),
            name=self.system["name"],
            sw_version=self.system.get("softwareversion"),
        )

    @property
    def system(self) -> SystemType:
        """Return the system descriptor."""
        if self.api.system:
            return self.api.system
        return self.config_entry.data[CONF_SYSTEM]

    @property
    def unique_id(self) -> str:
        """Return the system descriptor."""
        entry = self.config_entry
        if entry.unique_id:
            return entry.unique_id
        assert entry.entry_id
        return entry.entry_id

    @property
    def _notify_wanted(self):
        """Return if the notify feature should be active.

        We only run it when TV is considered fully on.
        When powerstate is in standby, the TV will go in low
        power states and seemingly break the http server in
        odd ways.
        """
        return (
            self.api.on
            and self.api.powerstate == "On"
            and self.api.notify_change_supported
            and self.config_entry.options.get(CONF_ALLOW_NOTIFY, False)
        )

    async def _notify_task(self):
        settings_version = self.api.settings_version
        while self._notify_wanted:
            try:
                res = await self.api.notifyChange(130)
            except ConnectionFailure, AutenticationFailure:
                res = None

            if res:
                if settings_version != self.api.settings_version:
                    settings_version = self.api.settings_version
                    await self._async_update_settings()
                self.async_set_updated_data(None)
            elif res is None:
                _LOGGER.debug("Aborting notify due to unexpected return")
                break

    @callback
    def _async_notify_stop(self):
        if self._notify_future:
            self._notify_future.cancel()
            self._notify_future = None

    @callback
    def _async_notify_schedule(self):
        if self._notify_future and not self._notify_future.done():
            return

        if self._notify_wanted:
            self._notify_future = asyncio.create_task(self._notify_task())

    @callback
    @override
    def _unschedule_refresh(self) -> None:
        """Remove data update."""
        super()._unschedule_refresh()
        self._async_notify_stop()

    async def _async_update_settings(self) -> None:
        """Fetch the values of the selected menu nodes."""
        if not (node_ids := self.get_selected_node_ids()):
            return
        if self.api.powerstate not in (TV_STATE_ON, None):
            return
        try:
            self.settings = await self.api.getMenuItemsSettingsCurrentValue(node_ids)
            await self.api.getStringsCached(
                string_id
                for description in self.settings_nodes
                for string_id in get_node_strings(description["node"])
            )
        except ConnectionFailure, GeneralFailure, KeyError:
            _LOGGER.debug("Unable to fetch the menu settings of the TV")
            self.settings = {}

    def get_string(self, string_id: str) -> str:
        """Return a cached translation."""
        return self.api.strings.get(string_id, string_id)

    def get_selected_node_ids(self) -> list[int]:
        """Return the ids of the selected menu nodes."""
        return [description["node"]["node_id"] for description in self.settings_nodes]

    @override
    async def _async_update_data(self):
        """Fetch the latest data from the source."""
        try:
            if await self.api.update():
                await self._async_update_settings()
            self._async_notify_schedule()
        except ConnectionFailure:
            pass
        except AutenticationFailure as exception:
            raise ConfigEntryAuthFailed(str(exception)) from exception
        except GeneralFailure as exception:
            raise UpdateFailed(str(exception)) from exception
