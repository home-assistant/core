"""Support for Alexa Devices."""

from asyncio import Lock
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import override

from aioamazondevices.api import AmazonEchoApi
from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
    NoOnlineDevicesError,
)
from aioamazondevices.structures import (
    AmazonDevice,
    AmazonListEvent,
    AmazonListEventType,
    AmazonListItem,
    AmazonMediaState,
    AmazonSaveDataConfig,
    AmazonVocalRecord,
    AmazonVolumeState,
)
from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import CONF_LOGIN_DATA, DOMAIN, LOGGER

SCAN_INTERVAL = 300


@asynccontextmanager
async def alexa_api_call(
    coordinator: DataUpdateCoordinator | None = None,
) -> AsyncGenerator[None]:
    """Handle common Alexa API exceptions as HomeAssistantError."""
    try:
        yield
    except CannotAuthenticate as err:
        if coordinator:
            coordinator.last_update_success = False
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"error": repr(err)},
        ) from err
    except CannotConnect as err:
        if coordinator:
            coordinator.last_update_success = False
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_with_error",
            translation_placeholders={"error": repr(err)},
        ) from err
    except (CannotRetrieveData, ValueError) as err:
        if coordinator:
            coordinator.last_update_success = False
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_retrieve_data_with_error",
            translation_placeholders={"error": repr(err)},
        ) from err


@asynccontextmanager
async def alexa_config_entry_errors() -> AsyncGenerator[None]:
    """Handle common Alexa API exceptions as ConfigEntry errors."""
    try:
        yield
    except CannotAuthenticate as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
            translation_placeholders={"error": repr(err)},
        ) from err
    except (CannotConnect, TimeoutError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect_with_error",
            translation_placeholders={"error": repr(err)},
        ) from err
    except (
        CannotRetrieveData,
        NoOnlineDevicesError,
        ValueError,
        KeyError,
        StopIteration,
    ) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_retrieve_data_with_error",
            translation_placeholders={"error": repr(err)},
        ) from err


type AmazonConfigEntry = ConfigEntry[AmazonDevicesCoordinator]


class AmazonDevicesCoordinator(DataUpdateCoordinator[dict[str, AmazonDevice]]):
    """Base coordinator for Alexa Devices."""

    config_entry: AmazonConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AmazonConfigEntry,
        session: ClientSession,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(
            hass,
            LOGGER,
            name=entry.title,
            config_entry=entry,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=SCAN_INTERVAL, immediate=False
            ),
        )
        self.api = AmazonEchoApi(
            session,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            login_data=entry.data[CONF_LOGIN_DATA],
            save_data=AmazonSaveDataConfig(
                path=Path(hass.config.path(DOMAIN)),
            ),
        )
        device_registry = dr.async_get(hass)
        self.previous_devices: set[str] = {
            identifier
            for device in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            )
            if device.entry_type != dr.DeviceEntryType.SERVICE
            for identifier_domain, identifier in device.identifiers
            if identifier_domain == DOMAIN
        }
        self.previous_routines: set[str] = {
            routine.unique_id
            for routine in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
            if routine.domain == Platform.BUTTON
        }
        self.previous_todo_lists: set[str] = {
            todo_list.unique_id
            for todo_list in er.async_entries_for_config_entry(
                er.async_get(hass), entry.entry_id
            )
            if todo_list.domain == Platform.TODO
        }

        self._todo_list_items: dict[str, dict[str, AmazonListItem]] = {}
        self._todo_refresh_lock = Lock()
        self.api.on_todo_event.append(self.todo_event_handler)
        self.api.on_todo_event.freeze()

        self._vocal_records: dict[str, AmazonVocalRecord] = {}
        self.api.on_history_event.append(self.history_state_event_handler)
        self.api.on_history_event.freeze()

        self._volume_states: dict[str, AmazonVolumeState] = {}
        self.api.on_volume_state_event.append(self.volume_state_event_handler)
        self.api.on_volume_state_event.freeze()

        self._media_states: dict[str, AmazonMediaState] = {}
        self.api.on_media_state_event.append(self.media_state_event_handler)
        self.api.on_media_state_event.freeze()

    @override
    async def _async_update_data(self) -> dict[str, AmazonDevice]:
        """Update device data."""
        try:
            await self.api.login.login_mode_stored_data()
            data = await self.api.get_devices_data()
        except CannotConnect as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except (CannotRetrieveData, NoOnlineDevicesError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_data_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except CannotAuthenticate as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except ValueError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_data_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        else:
            current_devices = set(data.keys())
            if stale_devices := self.previous_devices - current_devices:
                await self._async_remove_device_stale(stale_devices)
            self.previous_devices = current_devices

            current_routines = {
                f"{slugify(self.config_entry.unique_id)}-{slugify(routine)}"
                for routine in self.api.routines
            }
            if stale_routines := (self.previous_routines - current_routines):
                await self._async_remove_routine_stale(stale_routines)
            self.previous_routines = current_routines

            current_todo_lists = {
                f"{slugify(self.config_entry.unique_id)}-{todo_list.id}"
                for todo_list in self.api.todo_lists
            }
            if stale_todo_lists := self.previous_todo_lists - current_todo_lists:
                await self._async_remove_todo_lists_stale(stale_todo_lists)
            self.previous_todo_lists = current_todo_lists

            return data

    async def _async_remove_device_stale(
        self,
        stale_devices: set[str],
    ) -> None:
        """Remove stale device."""
        device_registry = dr.async_get(self.hass)

        for serial_num in stale_devices:
            LOGGER.debug(
                "Detected change in devices: serial %s removed",
                serial_num,
            )
            device = device_registry.async_get_device_by_identifier(
                (DOMAIN, serial_num), self.config_entry.entry_id
            )
            if device:
                device_registry.async_remove_device(device.id)

    async def _async_remove_routine_stale(
        self,
        stale_routines: set[str],
    ) -> None:
        """Remove stale routine."""
        entity_registry = er.async_get(self.hass)

        for routine_unique_id in stale_routines:
            entity_id = entity_registry.async_get_entity_id(
                Platform.BUTTON,
                DOMAIN,
                routine_unique_id,
            )
            if entity_id:
                LOGGER.debug(
                    "Detected change in routines: routine %s removed",
                    routine_unique_id.replace(
                        f"{slugify(self.config_entry.unique_id)}-", ""
                    ),
                )
                entity_registry.async_remove(entity_id)

    async def _async_remove_todo_lists_stale(
        self,
        stale_todo_lists: set[str],
    ) -> None:
        """Remove stale todo lists."""
        entity_registry = er.async_get(self.hass)

        for todo_list_unique_id in stale_todo_lists:
            entity_id = entity_registry.async_get_entity_id(
                Platform.TODO,
                DOMAIN,
                todo_list_unique_id,
            )
            if entity_id:
                LOGGER.debug(
                    "Detected change in todo lists: todo list entity %s removed",
                    entity_id,
                )
                entity_registry.async_remove(entity_id)
                list_id = todo_list_unique_id.replace(
                    f"{slugify(self.config_entry.unique_id)}-", ""
                )
                self._todo_list_items.pop(list_id, None)

    async def sync_todo_list_items(self) -> None:
        """Sync todo items. Only used for initial sync."""
        async with alexa_config_entry_errors():
            for todo_list in self.api.todo_lists:
                self._todo_list_items[
                    todo_list.id
                ] = await self.api.get_todo_list_items(todo_list.id)

    async def refresh_todo_list_items(self, list_id: str) -> None:
        """Refresh the cached items of a single to-do list.

        Cached items are otherwise only filled by the initial sync and by
        pushed events, so a write of our own needs a pull to become visible.

        The pulls are serialized, as an older answer landing last would leave
        the cache behind with nothing to repair it.
        """
        async with self._todo_refresh_lock, alexa_api_call(self):
            self._todo_list_items[list_id] = await self.api.get_todo_list_items(list_id)

            # Reading the list back proves the API answers again
            self.last_update_success = True

        self.async_update_listeners()

    async def todo_event_handler(self, list_event: AmazonListEvent) -> None:
        """Handle changes on To-Do lists.

        Takes the refresh lock, so an event arriving while a list is being
        read back is applied on top of that read instead of under it.
        """
        async with self._todo_refresh_lock:
            if list_event.type == AmazonListEventType.DELETED:
                self._todo_list_items.get(list_event.list_id, {}).pop(
                    list_event.item_id, None
                )
            elif (
                list_event.type
                in (AmazonListEventType.UPDATED, AmazonListEventType.CREATED)
            ) and list_event.items:
                if list_event.list_id not in self._todo_list_items:
                    # List was newly created after initial sync
                    self._todo_list_items[list_event.list_id] = {}

                self._todo_list_items[list_event.list_id][list_event.item_id] = (
                    list_event.items
                )

        self.async_update_listeners()

    @property
    def todo_list_items(self) -> dict[str, dict[str, AmazonListItem]]:
        """Current cached to-do list items (list_id -> item_id -> AmazonListItem)."""
        return self._todo_list_items

    async def sync_history_state(self) -> None:
        """Sync history state."""
        async with alexa_config_entry_errors():
            self._vocal_records = await self.api.sync_history_state()

    async def history_state_event_handler(
        self, vocal_records: dict[str, AmazonVocalRecord]
    ) -> None:
        """Handle pushed vocal record events."""
        self._vocal_records = {**self._vocal_records, **vocal_records}
        self.async_update_listeners()

    @property
    def vocal_records(self) -> dict[str, AmazonVocalRecord]:
        """Vocal records of devices."""
        return self._vocal_records

    async def sync_media_state(self) -> None:
        """Sync media state."""
        async with alexa_config_entry_errors():
            await self.api.sync_media_state()

    async def media_state_event_handler(
        self, media_state: dict[str, AmazonMediaState]
    ) -> None:
        """Handle pushed media state changed events."""
        self._media_states = media_state
        self.async_update_listeners()

    @property
    def media_states(self) -> dict[str, AmazonMediaState]:
        """Media state of devices."""
        return self._media_states

    async def volume_state_event_handler(
        self, volume_states: dict[str, AmazonVolumeState]
    ) -> None:
        """Handle pushed volume change events."""
        self._volume_states = volume_states
        self.async_update_listeners()

    @property
    def volume_states(self) -> dict[str, AmazonVolumeState]:
        """Volumes of devices."""
        return self._volume_states
