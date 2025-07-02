"""Coordinator for Home Connect."""

from __future__ import annotations

from asyncio import sleep as asyncio_sleep
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

from aiohomeconnect.client import Client as HomeConnectClient
from aiohomeconnect.model import (
    CommandKey,
    Event,
    EventKey,
    EventMessage,
    EventType,
    GetSetting,
    HomeAppliance,
    OptionKey,
    ProgramKey,
    SettingKey,
    Status,
    StatusKey,
)
from aiohomeconnect.model.error import (
    EventStreamInterruptedError,
    HomeConnectApiError,
    HomeConnectError,
    HomeConnectRequestError,
    TooManyRequestsError,
    UnauthorizedError,
)
from aiohomeconnect.model.program import EnumerateProgram, ProgramDefinitionOption
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_DEFAULT_RETRY_AFTER, APPLIANCES_WITH_PROGRAMS, DOMAIN
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

MAX_EXECUTIONS_TIME_WINDOW = 60 * 60  # 1 hour
MAX_EXECUTIONS = 8

type HomeConnectConfigEntry = ConfigEntry[HomeConnectCoordinator]


@dataclass(frozen=True, kw_only=True)
class HomeConnectApplianceData:
    """Class to hold Home Connect appliance data."""

    commands: set[CommandKey]
    events: dict[EventKey, Event]
    info: HomeAppliance
    options: dict[OptionKey, ProgramDefinitionOption]
    programs: list[EnumerateProgram]
    settings: dict[SettingKey, GetSetting]
    status: dict[StatusKey, Status]

    def update(self, other: HomeConnectApplianceData) -> None:
        """Update data with data from other instance."""
        self.commands.update(other.commands)
        self.events.update(other.events)
        self.info.connected = other.info.connected
        self.options.clear()
        self.options.update(other.options)
        self.programs.clear()
        self.programs.extend(other.programs)
        self.settings.update(other.settings)
        self.status.update(other.status)

    @classmethod
    def empty(cls, appliance: HomeAppliance) -> HomeConnectApplianceData:
        """Return empty data."""
        return cls(
            commands=set(),
            events={},
            info=appliance,
            options={},
            programs=[],
            settings={},
            status={},
        )


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
        self._special_listeners: dict[
            CALLBACK_TYPE, tuple[CALLBACK_TYPE, tuple[EventKey, ...]]
        ] = {}
        self.device_registry = dr.async_get(self.hass)
        self.data = {}
        self._execution_tracker: dict[str, list[float]] = defaultdict(list)

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
    def async_add_special_listener(
        self,
        update_callback: CALLBACK_TYPE,
        context: tuple[EventKey, ...],
    ) -> Callable[[], None]:
        """Listen for special data updates.

        These listeners will not be called on refresh.
        """

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._special_listeners.pop(remove_listener)
            if not self._special_listeners:
                self._unschedule_refresh()

        self._special_listeners[remove_listener] = (update_callback, context)

        return remove_listener

    @callback
    def start_event_listener(self) -> None:
        """Start event listener."""
        self.config_entry.async_create_background_task(
            self.hass,
            self._event_listener(),
            f"home_connect-events_listener_task-{self.config_entry.entry_id}",
        )

    async def _event_listener(self) -> None:  # noqa: C901
        """Match event with listener for event type."""
        retry_time = 10
        while True:
            try:
                async for event_message in self.client.stream_all_events():
                    retry_time = 10
                    event_message_ha_id = event_message.ha_id
                    if (
                        event_message_ha_id in self.data
                        and not self.data[event_message_ha_id].info.connected
                    ):
                        self.data[event_message_ha_id].info.connected = True
                        self._call_all_event_listeners_for_appliance(
                            event_message_ha_id
                        )
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
                                event_key = event.key
                                if event_key in SettingKey.__members__.values():  # type: ignore[comparison-overlap]
                                    setting_key = SettingKey(event_key)
                                    if setting_key in settings:
                                        settings[setting_key].value = event.value
                                    else:
                                        settings[setting_key] = GetSetting(
                                            key=setting_key,
                                            raw_key=setting_key.value,
                                            value=event.value,
                                        )
                                else:
                                    if event_key in (
                                        EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
                                        EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
                                    ):
                                        await self.update_options(
                                            event_message_ha_id,
                                            event_key,
                                            ProgramKey(cast(str, event.value)),
                                        )
                                    events[event_key] = event
                            self._call_event_listener(event_message)

                        case EventType.EVENT:
                            events = self.data[event_message_ha_id].events
                            for event in event_message.data.items:
                                events[event.key] = event
                            self._call_event_listener(event_message)

                        case EventType.CONNECTED | EventType.PAIRED:
                            if self.refreshed_too_often_recently(event_message_ha_id):
                                continue

                            appliance_info = await self.client.get_specific_appliance(
                                event_message_ha_id
                            )

                            appliance_data = await self._get_appliance_data(
                                appliance_info, self.data.get(appliance_info.ha_id)
                            )
                            if event_message_ha_id not in self.data:
                                self.data[event_message_ha_id] = appliance_data
                            for listener, context in self._special_listeners.values():
                                if (
                                    EventKey.BSH_COMMON_APPLIANCE_DEPAIRED
                                    not in context
                                ):
                                    listener()
                            self._call_all_event_listeners_for_appliance(
                                event_message_ha_id
                            )

                        case EventType.DISCONNECTED:
                            self.data[event_message_ha_id].info.connected = False
                            self._call_all_event_listeners_for_appliance(
                                event_message_ha_id
                            )

                        case EventType.DEPAIRED:
                            device = self.device_registry.async_get_device(
                                identifiers={(DOMAIN, event_message_ha_id)}
                            )
                            if device:
                                self.device_registry.async_update_device(
                                    device_id=device.id,
                                    remove_config_entry_id=self.config_entry.entry_id,
                                )
                            self.data.pop(event_message_ha_id, None)
                            for listener, context in self._special_listeners.values():
                                assert isinstance(context, tuple)
                                if EventKey.BSH_COMMON_APPLIANCE_DEPAIRED in context:
                                    listener()

            except (EventStreamInterruptedError, HomeConnectRequestError) as error:
                _LOGGER.debug(
                    "Non-breaking error (%s) while listening for events,"
                    " continuing in %s seconds",
                    error,
                    retry_time,
                )
                await asyncio_sleep(retry_time)
                retry_time = min(retry_time * 2, 3600)
            except HomeConnectApiError as error:
                _LOGGER.error("Error while listening for events: %s", error)
                self.hass.config_entries.async_schedule_reload(
                    self.config_entry.entry_id
                )
                break

    @callback
    def _call_event_listener(self, event_message: EventMessage) -> None:
        """Call listener for event."""
        for event in event_message.data.items:
            for listener in self.context_listeners.get(
                (event_message.ha_id, event.key), []
            ):
                listener()

    @callback
    def _call_all_event_listeners_for_appliance(self, ha_id: str) -> None:
        for listener, context in self._listeners.values():
            if isinstance(context, tuple) and context[0] == ha_id:
                listener()

    async def _async_update_data(self) -> dict[str, HomeConnectApplianceData]:
        """Fetch data from Home Connect."""
        await self._async_setup()

        for appliance_data in self.data.values():
            appliance = appliance_data.info
            ha_id = appliance.ha_id
            while True:
                try:
                    self.data[ha_id] = await self._get_appliance_data(
                        appliance, self.data.get(ha_id)
                    )
                except TooManyRequestsError as err:
                    _LOGGER.debug(
                        "Rate limit exceeded on initial fetch: %s",
                        err,
                    )
                    await asyncio_sleep(err.retry_after or API_DEFAULT_RETRY_AFTER)
                else:
                    break

        for listener, context in self._special_listeners.values():
            assert isinstance(context, tuple)
            if EventKey.BSH_COMMON_APPLIANCE_PAIRED in context:
                listener()

        return self.data

    async def async_setup(self) -> None:
        """Set up the devices."""
        try:
            await self._async_setup()
        except UpdateFailed as err:
            raise ConfigEntryNotReady from err

    async def _async_setup(self) -> None:
        """Set up the devices."""
        old_appliances = set(self.data.keys())
        try:
            appliances = await self.client.get_home_appliances()
        except UnauthorizedError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders=get_dict_from_home_connect_error(error),
            ) from error
        except HomeConnectError as error:
            for appliance_data in self.data.values():
                appliance_data.info.connected = False
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="fetch_api_error",
                translation_placeholders=get_dict_from_home_connect_error(error),
            ) from error

        for appliance in appliances.homeappliances:
            self.device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                identifiers={(DOMAIN, appliance.ha_id)},
                manufacturer=appliance.brand,
                name=appliance.name,
                model=appliance.vib,
            )
            if appliance.ha_id not in self.data:
                self.data[appliance.ha_id] = HomeConnectApplianceData.empty(appliance)
            else:
                self.data[appliance.ha_id].info.connected = appliance.connected
                old_appliances.remove(appliance.ha_id)

        for ha_id in old_appliances:
            self.data.pop(ha_id, None)
            device = self.device_registry.async_get_device(
                identifiers={(DOMAIN, ha_id)}
            )
            if device:
                self.device_registry.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

        # Trigger to delete the possible depaired device entities
        # from known_entities variable at common.py
        for listener, context in self._special_listeners.values():
            assert isinstance(context, tuple)
            if EventKey.BSH_COMMON_APPLIANCE_DEPAIRED in context:
                listener()

    async def _get_appliance_data(
        self,
        appliance: HomeAppliance,
        appliance_data_to_update: HomeConnectApplianceData | None = None,
    ) -> HomeConnectApplianceData:
        """Get appliance data."""
        self.device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, appliance.ha_id)},
            manufacturer=appliance.brand,
            name=appliance.name,
            model=appliance.vib,
        )
        if not appliance.connected:
            _LOGGER.debug(
                "Appliance %s is not connected, skipping data fetch",
                appliance.ha_id,
            )
            if appliance_data_to_update:
                appliance_data_to_update.info.connected = False
                return appliance_data_to_update
            return HomeConnectApplianceData.empty(appliance)
        try:
            settings = {
                setting.key: setting
                for setting in (
                    await self.client.get_settings(appliance.ha_id)
                ).settings
            }
        except TooManyRequestsError:
            raise
        except HomeConnectError as error:
            _LOGGER.debug(
                "Error fetching settings for %s: %s",
                appliance.ha_id,
                error,
            )
            settings = {}
        try:
            status = {
                status.key: status
                for status in (await self.client.get_status(appliance.ha_id)).status
            }
        except TooManyRequestsError:
            raise
        except HomeConnectError as error:
            _LOGGER.debug(
                "Error fetching status for %s: %s",
                appliance.ha_id,
                error,
            )
            status = {}

        programs = []
        events = {}
        options = {}
        if appliance.type in APPLIANCES_WITH_PROGRAMS:
            try:
                all_programs = await self.client.get_all_programs(appliance.ha_id)
            except TooManyRequestsError:
                raise
            except HomeConnectError as error:
                _LOGGER.debug(
                    "Error fetching programs for %s: %s",
                    appliance.ha_id,
                    error,
                )
            else:
                programs.extend(all_programs.programs)
                current_program_key = None
                program_options = None
                for program, event_key in (
                    (
                        all_programs.selected,
                        EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM,
                    ),
                    (
                        all_programs.active,
                        EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM,
                    ),
                ):
                    if program and program.key:
                        events[event_key] = Event(
                            event_key,
                            event_key.value,
                            0,
                            "",
                            "",
                            program.key,
                        )
                        current_program_key = program.key
                        program_options = program.options
                if current_program_key:
                    options = await self.get_options_definitions(
                        appliance.ha_id, current_program_key
                    )
                    for option in program_options or []:
                        option_event_key = EventKey(option.key)
                        events[option_event_key] = Event(
                            option_event_key,
                            option.key,
                            0,
                            "",
                            "",
                            option.value,
                            option.name,
                            display_value=option.display_value,
                            unit=option.unit,
                        )

        try:
            commands = {
                command.key
                for command in (
                    await self.client.get_available_commands(appliance.ha_id)
                ).commands
            }
        except TooManyRequestsError:
            raise
        except HomeConnectError:
            commands = set()

        appliance_data = HomeConnectApplianceData(
            commands=commands,
            events=events,
            info=appliance,
            options=options,
            programs=programs,
            settings=settings,
            status=status,
        )
        if appliance_data_to_update:
            appliance_data_to_update.update(appliance_data)
            appliance_data = appliance_data_to_update

        return appliance_data

    async def get_options_definitions(
        self, ha_id: str, program_key: ProgramKey
    ) -> dict[OptionKey, ProgramDefinitionOption]:
        """Get options with constraints for appliance."""
        if program_key is ProgramKey.UNKNOWN:
            return {}
        try:
            return {
                option.key: option
                for option in (
                    await self.client.get_available_program(
                        ha_id, program_key=program_key
                    )
                ).options
                or []
            }
        except TooManyRequestsError:
            raise
        except HomeConnectError as error:
            _LOGGER.debug(
                "Error fetching options for %s: %s",
                ha_id,
                error,
            )
            return {}

    async def update_options(
        self, ha_id: str, event_key: EventKey, program_key: ProgramKey
    ) -> None:
        """Update options for appliance."""
        options = self.data[ha_id].options
        events = self.data[ha_id].events
        options_to_notify = options.copy()
        options.clear()
        options.update(await self.get_options_definitions(ha_id, program_key))

        for option in options.values():
            option_value = option.constraints.default if option.constraints else None
            if option_value is not None:
                option_event_key = EventKey(option.key)
                events[option_event_key] = Event(
                    option_event_key,
                    option.key.value,
                    0,
                    "",
                    "",
                    option_value,
                    option.name,
                    unit=option.unit,
                )
        options_to_notify.update(options)
        for option_key in options_to_notify:
            for listener in self.context_listeners.get(
                (ha_id, EventKey(option_key)),
                [],
            ):
                listener()

    def refreshed_too_often_recently(self, appliance_ha_id: str) -> bool:
        """Check if the appliance data hasn't been refreshed too often recently."""

        now = self.hass.loop.time()
        if len(self._execution_tracker[appliance_ha_id]) >= MAX_EXECUTIONS:
            return True

        execution_tracker = self._execution_tracker[appliance_ha_id] = [
            timestamp
            for timestamp in self._execution_tracker[appliance_ha_id]
            if now - timestamp < MAX_EXECUTIONS_TIME_WINDOW
        ]

        execution_tracker.append(now)

        if len(execution_tracker) >= MAX_EXECUTIONS:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"home_connect_too_many_connected_paired_events_{appliance_ha_id}",
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="home_connect_too_many_connected_paired_events",
                data={
                    "entry_id": self.config_entry.entry_id,
                    "appliance_ha_id": appliance_ha_id,
                },
                translation_placeholders={
                    "appliance_name": self.data[appliance_ha_id].info.name,
                    "times": str(MAX_EXECUTIONS),
                    "time_window": str(MAX_EXECUTIONS_TIME_WINDOW // 60),
                    "home_connect_resource_url": "https://www.home-connect.com/global/help-support/error-codes#/Togglebox=15362315-13320636-1/",
                    "home_assistant_core_new_issue_url": (
                        "https://github.com/home-assistant/core/issues/new?template=bug_report.yml"
                        f"&integration_name={DOMAIN}&integration_link=https://www.home-assistant.io/integrations/{DOMAIN}/"
                    ),
                },
            )
            return True

        return False

    async def reset_execution_tracker(self, appliance_ha_id: str) -> None:
        """Reset the execution tracker for a specific appliance."""
        self._execution_tracker.pop(appliance_ha_id, None)
        appliance_info = await self.client.get_specific_appliance(appliance_ha_id)

        appliance_data = await self._get_appliance_data(
            appliance_info, self.data.get(appliance_info.ha_id)
        )
        self.data[appliance_ha_id].update(appliance_data)
        for listener, context in self._special_listeners.values():
            if EventKey.BSH_COMMON_APPLIANCE_DEPAIRED not in context:
                listener()
        self._call_all_event_listeners_for_appliance(appliance_ha_id)
