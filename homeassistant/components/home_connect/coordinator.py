"""Coordinator for Home Connect."""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
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

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

type HomeConnectConfigEntry = ConfigEntry[HomeConnectCoordinator]

EVENT_STREAM_RECONNECT_DELAY = 30


@dataclass(frozen=True, kw_only=True)
class HomeConnectApplianceData:
    """Class to hold Home Connect appliance data."""

    info: HomeAppliance
    settings: dict[SettingKey, GetSetting]
    status: dict[StatusKey, Status]


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
        self.client: HomeConnectClient = client
        self._home_appliances_event_listeners: dict[
            str, dict[EventKey, list[Callable[[Event], Coroutine[Any, Any, None]]]]
        ] = {}

    async def start_event_listener(self) -> None:
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
                    match event_message.type:
                        case EventType.STATUS:
                            statuses = self.data[event_message.ha_id].status
                            for event in event_message.data.items:
                                if (
                                    event.key not in StatusKey
                                    or event.key is EventKey.UNKNOWN
                                ):
                                    continue
                                status_key = StatusKey(event.key)
                                if status_key in statuses:
                                    statuses[status_key].value = event.value
                                else:
                                    statuses[status_key] = Status(
                                        status_key, event.value
                                    )
                            await self._call_event_listener(event_message)

                        case EventType.NOTIFY:
                            settings = self.data[event_message.ha_id].settings
                            for event in event_message.data.items:
                                if (
                                    event.key not in SettingKey
                                    or event.key is EventKey.UNKNOWN
                                ):
                                    continue
                                setting_key = SettingKey(event.key)
                                if setting_key in settings:
                                    settings[setting_key].value = event.value
                                else:
                                    settings[setting_key] = GetSetting(
                                        setting_key, event.value
                                    )
                            await self._call_event_listener(event_message)

                        case EventType.EVENT:
                            await self._call_event_listener(event_message)

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

    async def _call_event_listener(self, event_message: EventMessage):
        """Call listener for event."""
        listeners = self._home_appliances_event_listeners.get(event_message.ha_id, {})
        if not listeners:
            return
        for event in event_message.data.items:
            if event.key is EventKey.UNKNOWN:
                continue
            for listener in listeners.get(event.key, []):
                await listener(event)

    def add_home_appliances_event_listener(
        self,
        ha_id: str,
        event_key: EventKey,
        cb: Callable[[Event], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a event listener for a specific home appliance and event key."""
        self._home_appliances_event_listeners.setdefault(ha_id, {}).setdefault(
            event_key, []
        ).append(cb)

    def delete_home_appliances_event_listener(
        self,
        ha_id: str,
        event_key: EventKey,
        cb: Callable[[Event], Coroutine[Any, Any, None]],
    ) -> None:
        """Deregister event listener for a specific home appliance and event key."""
        if (
            ha_id in self._home_appliances_event_listeners
            and event_key in self._home_appliances_event_listeners[ha_id]
        ):
            appliance_listeners = self._home_appliances_event_listeners[ha_id]
            if cb in (
                listeners := self._home_appliances_event_listeners[ha_id][event_key]
            ):
                listeners.remove(cb)
            if not listeners:
                self._home_appliances_event_listeners[ha_id].pop(event_key)
            if not appliance_listeners:
                self._home_appliances_event_listeners.pop(ha_id)

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

        appliance_data = {}
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
            appliance_data[appliance.ha_id] = HomeConnectApplianceData(
                info=appliance, settings=settings, status=status
            )
        return appliance_data
