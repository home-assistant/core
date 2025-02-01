"""Coordinator for Home Connect."""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any

from aiohomeconnect.client import Client as HomeConnectClient
from aiohomeconnect.model import (
    Event,
    EventKey,
    EventMessage,
    EventType,
    GetSetting,
    HomeAppliance,
    SettingKey,
    Status,
    StatusKey,
)
from aiohomeconnect.model.error import (
    EventStreamInterruptedError,
    HomeConnectApiError,
    HomeConnectError,
    HomeConnectRequestError,
)
from aiohomeconnect.model.program import EnumerateProgram
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import APPLIANCES_WITH_PROGRAMS, DOMAIN
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

type HomeConnectConfigEntry = ConfigEntry[HomeConnectCoordinator]

EVENT_STREAM_RECONNECT_DELAY = 30


@dataclass(frozen=True, kw_only=True)
class HomeConnectApplianceData:
    """Class to hold Home Connect appliance data."""

    events: dict[EventKey, Event] = field(default_factory=dict)
    info: HomeAppliance
    programs: list[EnumerateProgram] = field(default_factory=list)
    settings: dict[SettingKey, GetSetting]
    status: dict[StatusKey, Status]

    def update(self, other: "HomeConnectApplianceData") -> None:
        """Update data with data from other instance."""
        self.events.update(other.events)
        self.info.connected = other.info.connected
        self.programs.clear()
        self.programs.extend(other.programs)
        self.settings.update(other.settings)
        self.status.update(other.status)


class HomeConnectCoordinator(
    DataUpdateCoordinator[dict[str, HomeConnectApplianceData]]
):
    """Class to manage fetching Home Connect data."""

    config_entry: HomeConnectConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HomeConnectConfigEntry,
        client: HomeConnectClient,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.entry_id,
        )
        self.client = client

    @cached_property
    def context_listeners(self) -> dict[tuple[str, EventKey], list[CALLBACK_TYPE]]:
        """Return a dict of all listeners registered for a given context."""
        listeners: dict[tuple[str, EventKey], list[CALLBACK_TYPE]] = defaultdict(list)
        for listener, context in list(self._listeners.values()):
            assert isinstance(context, tuple)
            listeners[context].append(listener)
        return listeners

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listen for data updates."""
        remove_listener = super().async_add_listener(update_callback, context)
        self.__dict__.pop("context_listeners", None)

        def remove_listener_and_invalidate_context_listeners() -> None:
            remove_listener()
            self.__dict__.pop("context_listeners", None)

        return remove_listener_and_invalidate_context_listeners

    @callback
    def start_event_listener(self) -> None:
        """Start event listener."""
        self.config_entry.async_create_background_task(
            self.hass,
            self._event_listener(),
            f"home_connect-events_listener_task-{self.config_entry.entry_id}",
        )

    async def _event_listener(self) -> None:
        """Match event with listener for event type."""
        while True:
            try:
                async for event_message in self.client.stream_all_events():
                    event_message_ha_id = event_message.ha_id
                    match event_message.type:
                        case EventType.STATUS:
                            statuses = self.data[event_message_ha_id].status
                            for event in event_message.data.items:
                                status_key = StatusKey(event.key)
                                if status_key in statuses:
                                    statuses[status_key].value = event.value
                                else:
                                    statuses[status_key] = Status(
                                        key=status_key,
                                        raw_key=status_key.value,
                                        value=event.value,
                                    )
                            self._call_event_listener(event_message)

                        case EventType.NOTIFY:
                            settings = self.data[event_message_ha_id].settings
                            events = self.data[event_message_ha_id].events
                            for event in event_message.data.items:
                                if event.key in SettingKey:
                                    setting_key = SettingKey(event.key)
                                    if setting_key in settings:
                                        settings[setting_key].value = event.value
                                    else:
                                        settings[setting_key] = GetSetting(
                                            key=setting_key,
                                            raw_key=setting_key.value,
                                            value=event.value,
                                        )
                                else:
                                    events[event.key] = event
                            self._call_event_listener(event_message)

                        case EventType.EVENT:
                            events = self.data[event_message_ha_id].events
                            for event in event_message.data.items:
                                events[event.key] = event
                            self._call_event_listener(event_message)

                        case EventType.CONNECTED:
                            self.data[event_message_ha_id].info.connected = True
                            self._call_all_event_listeners_for_appliance(
                                event_message_ha_id
                            )

                        case EventType.DISCONNECTED:
                            self.data[event_message_ha_id].info.connected = False
                            self._call_all_event_listeners_for_appliance(
                                event_message_ha_id
                            )

            except (EventStreamInterruptedError, HomeConnectRequestError) as error:
                _LOGGER.debug(
                    "Non-breaking error (%s) while listening for events,"
                    " continuing in 30 seconds",
                    type(error).__name__,
                )
                await asyncio.sleep(EVENT_STREAM_RECONNECT_DELAY)
            except HomeConnectApiError as error:
                _LOGGER.error("Error while listening for events: %s", error)
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
                break
            # if there was a non-breaking error, we continue listening
            # but we need to refresh the data to get the possible changes
            # that happened while the event stream was interrupted
            await self.async_refresh()

    @callback
    def _call_event_listener(self, event_message: EventMessage):
        """Call listener for event."""
        for event in event_message.data.items:
            for listener in self.context_listeners.get(
                (event_message.ha_id, event.key), []
            ):
                listener()

    @callback
    def _call_all_event_listeners_for_appliance(self, ha_id: str):
        for listener, context in self._listeners.values():
            if isinstance(context, tuple) and context[0] == ha_id:
                listener()

    async def _async_update_data(self) -> dict[str, HomeConnectApplianceData]:
        """Fetch data from Home Connect."""
        try:
            appliances = await self.client.get_home_appliances()
        except HomeConnectError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="fetch_api_error",
                translation_placeholders=get_dict_from_home_connect_error(error),
            ) from error

        appliances_data = self.data or {}
        for appliance in appliances.homeappliances:
            try:
                settings = {
                    setting.key: setting
                    for setting in (
                        await self.client.get_settings(appliance.ha_id)
                    ).settings
                }
            except HomeConnectError as error:
                _LOGGER.debug(
                    "Error fetching settings for %s: %s",
                    appliance.ha_id,
                    error
                    if isinstance(error, HomeConnectApiError)
                    else type(error).__name__,
                )
                settings = {}
            try:
                status = {
                    status.key: status
                    for status in (await self.client.get_status(appliance.ha_id)).status
                }
            except HomeConnectError as error:
                _LOGGER.debug(
                    "Error fetching status for %s: %s",
                    appliance.ha_id,
                    error
                    if isinstance(error, HomeConnectApiError)
                    else type(error).__name__,
                )
                status = {}
            appliance_data = HomeConnectApplianceData(
                info=appliance, settings=settings, status=status
            )
            if appliance.ha_id in appliances_data:
                appliances_data[appliance.ha_id].update(appliance_data)
                appliance_data = appliances_data[appliance.ha_id]
            else:
                appliances_data[appliance.ha_id] = appliance_data
            if (
                appliance.type in APPLIANCES_WITH_PROGRAMS
                and not appliance_data.programs
            ):
                try:
                    appliance_data.programs.extend(
                        (await self.client.get_all_programs(appliance.ha_id)).programs
                    )
                except HomeConnectError as error:
                    _LOGGER.debug(
                        "Error fetching programs for %s: %s",
                        appliance.ha_id,
                        error
                        if isinstance(error, HomeConnectApiError)
                        else type(error).__name__,
                    )
        return appliances_data
