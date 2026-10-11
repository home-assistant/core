"""Coordinator for the Philips TV integration."""

import asyncio
from datetime import timedelta
import logging
from typing import override

from haphilipsjs import (
    AutenticationFailure,
    ConnectionFailure,
    GeneralFailure,
    PhilipsTV,
)
from haphilipsjs.typing import (
    MenuItemsSettingsCurrentValueValue,
    MenuItemsSettingsUpdateValueData,
    SystemType,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ALLOW_NOTIFY, CONF_MENU_NODES, CONF_SYSTEM, DOMAIN
from .helpers import (
    EntitySetupData,
    MenuData,
    SettingsNotAvailable,
    async_fetch_menu_data,
    get_menu_nodes,
)

_LOGGER = logging.getLogger(__name__)

MENU_STORAGE_VERSION = 1


def get_menu_store(hass: HomeAssistant, entry_id: str) -> Store[MenuData]:
    """Return the store holding the cached menu structure of an entry."""
    return Store(hass, MENU_STORAGE_VERSION, f"{DOMAIN}.{entry_id}.menu")


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
        self.menu: MenuData | None = None
        self._menu_store = get_menu_store(hass, config_entry.entry_id)
        # The api replaces this object when it reads the structure again
        self._menu_source: object | None = None

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
            name=self.system.get("name"),
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
                    try:
                        await self._async_update_settings()
                    except GeneralFailure:
                        _LOGGER.debug("Aborting notify due to failed settings update")
                        break
                    settings_version = self.api.settings_version
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

    @property
    def menu_nodes(self) -> dict[int, EntitySetupData]:
        """Return the menu nodes that can be exposed as entities."""
        if self.menu is None:
            return {}
        return get_menu_nodes(self.menu)

    @property
    def selected_menu_nodes(self) -> list[EntitySetupData]:
        """Return the menu nodes selected in options and known by the TV."""
        menu_nodes = self.menu_nodes
        return [
            menu_nodes[node_id]
            for node_id in self.config_entry.options.get(CONF_MENU_NODES, [])
            if node_id in menu_nodes
        ]

    @callback
    def _async_log_missing_menu_nodes(self) -> None:
        if self.menu is None:
            return
        menu_nodes = self.menu_nodes
        if missing := [
            node_id
            for node_id in self.config_entry.options.get(CONF_MENU_NODES, [])
            if node_id not in menu_nodes
        ]:
            _LOGGER.warning(
                "Selected menu settings %s are no longer provided by the TV", missing
            )

    @override
    async def _async_setup(self) -> None:
        """Load the cached menu structure."""
        self.menu = await self._menu_store.async_load()
        self._async_log_missing_menu_nodes()

    async def _async_update_menu(self) -> None:
        """Refresh the cached menu structure when the TV provides a new one."""
        if (source := self.api.settings) is None or source is self._menu_source:
            return

        try:
            menu = await async_fetch_menu_data(self.api)
        except SettingsNotAvailable as err:
            _LOGGER.debug("Unable to read menu structure: %s", err)
            return
        self._menu_source = source

        if menu == self.menu:
            return

        selected_menu_nodes = self.selected_menu_nodes
        self.menu = menu
        await self._menu_store.async_save(menu)
        self._async_log_missing_menu_nodes()

        # Entities are created from the menu, so they need to be set up again
        if (
            self.config_entry.state is ConfigEntryState.LOADED
            and self.selected_menu_nodes != selected_menu_nodes
        ):
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    async def _async_update_settings(self) -> None:
        node_ids = [
            description["node"]["node_id"] for description in self.selected_menu_nodes
        ]
        if settings := await self.api.getMenuItemsSettingsCurrentValue(node_ids):
            self.settings = settings
        else:
            self.settings = {}

    async def async_update_menu_setting(
        self, node_id: int, data: MenuItemsSettingsUpdateValueData
    ) -> None:
        """Send a new value for a menu setting to the TV."""
        try:
            result = await self.api.postMenuItemsSettingsUpdateData({node_id: data})
        except GeneralFailure as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err
        # A failed request without exception is reported as None
        if result is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="update_failed"
            )

        # A change can affect value and availability of other settings
        try:
            await self._async_update_settings()
        except GeneralFailure:
            await self.async_request_refresh()
            return
        self.async_update_listeners()

    async def _async_update_menu_settings(self) -> None:
        """Refresh the menu and settings, failures only affect menu entities."""
        try:
            await self._async_update_menu()
            await self._async_update_settings()
        except AutenticationFailure:
            raise
        except GeneralFailure as err:
            _LOGGER.debug("Unable to read menu settings: %s", err)
            self.settings = {}

    @override
    async def _async_update_data(self):
        """Fetch the latest data from the source."""
        try:
            if await self.api.update():
                await self._async_update_menu_settings()
            self._async_notify_schedule()
        except ConnectionFailure:
            pass
        except AutenticationFailure as exception:
            raise ConfigEntryAuthFailed(str(exception)) from exception
        except GeneralFailure as exception:
            raise UpdateFailed(str(exception)) from exception

    def get_string(self, string_id: str) -> str:
        """Get a translation from the cached menu structure."""
        if self.menu is None:
            return string_id
        return self.menu["strings"].get(string_id, string_id)
