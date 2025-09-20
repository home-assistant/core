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
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_DEFAULT_RETRY_AFTER,
    APPLIANCES_WITH_PROGRAMS,
    BSH_OPERATION_STATE_PAUSE,
    DOMAIN,
)
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
        self.commands.clear()
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


class HomeConnectCoordinator:
    """Class to manage fetching Home Connect data."""

    config_entry: HomeConnectConfigEntry
    appliance_coordinators: dict[str, HomeConnectApplianceCoordinator]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HomeConnectConfigEntry,
        client: HomeConnectClient,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.config_entry = config_entry
        self.client = client
        self.global_listeners: dict[
            CALLBACK_TYPE, tuple[CALLBACK_TYPE, tuple[EventKey, ...]]
        ] = {}
        self.device_registry = dr.async_get(self.hass)
        self._execution_tracker: list[float] = []
        self.appliance_coordinators = {}

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
        retry_time = 10
        while True:
            try:
                async for event_message in self.client.stream_all_events():
                    retry_time = 10
                    event_message_ha_id = event_message.ha_id
                    if event_message_ha_id in self.appliance_coordinators:
                        if event_message.type == EventType.DEPAIRED:
                            appliance_coordinator = self.appliance_coordinators.pop(
                                event_message.ha_id
                            )
                        else:
                            appliance_coordinator = self.appliance_coordinators[
                                event_message.ha_id
                            ]
                        if not appliance_coordinator.data.info.connected:
                            appliance_coordinator.data.info.connected = True
                            appliance_coordinator.call_all_event_listeners()

                    elif event_message.type == EventType.PAIRED:
                        appliance_coordinator = self.appliance_coordinators[
                            event_message.ha_id
                        ] = HomeConnectApplianceCoordinator(
                            self.hass,
                            self.config_entry,
                            self.client,
                            await self.client.get_specific_appliance(
                                event_message_ha_id
                            ),
                        )

                    assert appliance_coordinator
                    await appliance_coordinator.event_listener(event_message)

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
    def async_add_global_listener(
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
            self.global_listeners.pop(remove_listener)

        self.global_listeners[remove_listener] = (update_callback, context)

        return remove_listener

    async def async_setup(self) -> None:
        """Set up the devices."""
        try:
            appliances = await self.client.get_home_appliances()
        except UnauthorizedError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders=get_dict_from_home_connect_error(error),
            ) from error
        except HomeConnectError as error:
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
            self.appliance_coordinators[appliance.ha_id] = (
                HomeConnectApplianceCoordinator(
                    self.hass,
                    self.config_entry,
                    self.client,
                    appliance,
                )
            )


class HomeConnectApplianceCoordinator(DataUpdateCoordinator[HomeConnectApplianceData]):
    """Class to manage fetching Home Connect appliance data."""

    config_entry: HomeConnectConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HomeConnectConfigEntry,
        client: HomeConnectClient,
        appliance: HomeAppliance,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.entry_id,
        )
        self.client = client
        self.device_registry = dr.async_get(self.hass)
        self.data = HomeConnectApplianceData.empty(appliance)
        self._execution_tracker: list[float] = []

    @cached_property
    def context_listeners(self) -> dict[EventKey, list[CALLBACK_TYPE]]:
        """Return a dict of all listeners registered for a given context."""
        listeners: dict[EventKey, list[CALLBACK_TYPE]] = defaultdict(list)
        for listener, context in list(self._listeners.values()):
            if isinstance(context, EventKey):
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

    async def event_listener(self, event_message: EventMessage) -> None:
        """Match event with listener for event type."""

        match event_message.type:
            case EventType.STATUS:
                statuses = self.data.status
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
                    if (
                        status_key == StatusKey.BSH_COMMON_OPERATION_STATE
                        and event.value == BSH_OPERATION_STATE_PAUSE
                        and CommandKey.BSH_COMMON_RESUME_PROGRAM
                        not in (commands := self.data.commands)
                    ):
                        # All the appliances that can be paused
                        # should have the resume command available.
                        commands.add(CommandKey.BSH_COMMON_RESUME_PROGRAM)
                        for (
                            listener,
                            context,
                        ) in self.config_entry.runtime_data.global_listeners.values():
                            if EventKey.BSH_COMMON_APPLIANCE_DEPAIRED not in context:
                                listener()
                self._call_event_listener(event_message)

            case EventType.NOTIFY:
                settings = self.data.settings
                events = self.data.events
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
                                event_key,
                                ProgramKey(cast(str, event.value)),
                            )
                        events[event_key] = event
                self._call_event_listener(event_message)

            case EventType.EVENT:
                events = self.data.events
                for event in event_message.data.items:
                    events[event.key] = event
                self._call_event_listener(event_message)

            case EventType.CONNECTED | EventType.PAIRED:
                if self.refreshed_too_often_recently():
                    return

                await self.get_appliance_data()
                for (
                    listener,
                    context,
                ) in self.config_entry.runtime_data.global_listeners.values():
                    if EventKey.BSH_COMMON_APPLIANCE_DEPAIRED not in context:
                        listener()
                self.call_all_event_listeners()

            case EventType.DISCONNECTED:
                self.data.info.connected = False
                self.call_all_event_listeners()

            case EventType.DEPAIRED:
                device = self.device_registry.async_get_device(
                    identifiers={(DOMAIN, self.data.info.ha_id)}
                )
                if device:
                    self.device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
                for (
                    listener,
                    context,
                ) in self.config_entry.runtime_data.global_listeners.values():
                    assert isinstance(context, tuple)
                    if EventKey.BSH_COMMON_APPLIANCE_DEPAIRED in context:
                        listener()

    @callback
    def _call_event_listener(self, event_message: EventMessage) -> None:
        """Call listener for event."""
        for event in event_message.data.items:
            for listener in self.context_listeners.get(event.key, []):
                listener()

    @callback
    def call_all_event_listeners(self) -> None:
        """Call all listeners."""
        for listener, _ in self._listeners.values():
            listener()

    async def _async_update_data(self) -> HomeConnectApplianceData:
        """Fetch data from Home Connect."""
        while True:
            try:
                self.data.info.connected = (
                    await self.client.get_specific_appliance(self.data.info.ha_id)
                ).connected
                await self.get_appliance_data()
            except TooManyRequestsError as err:
                _LOGGER.debug(
                    "Rate limit exceeded on initial fetch: %s",
                    err,
                )
                await asyncio_sleep(err.retry_after or API_DEFAULT_RETRY_AFTER)
            except UnauthorizedError as error:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_error",
                    translation_placeholders=get_dict_from_home_connect_error(error),
                ) from error
            except HomeConnectError as error:
                self.data.info.connected = False
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="fetch_api_error",
                    translation_placeholders=get_dict_from_home_connect_error(error),
                ) from error
            else:
                break

        for (
            listener,
            context,
        ) in self.config_entry.runtime_data.global_listeners.values():
            assert isinstance(context, tuple)
            if EventKey.BSH_COMMON_APPLIANCE_PAIRED in context:
                listener()

        return self.data

    async def get_appliance_data(self) -> None:
        """Get appliance data."""
        appliance = self.data.info
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
            self.data.update(HomeConnectApplianceData.empty(appliance))
            return
        settings = {
            setting.key: setting
            for setting in (await self.client.get_settings(appliance.ha_id)).settings
        }
        status = {
            status.key: status
            for status in (await self.client.get_status(appliance.ha_id)).status
        }

        programs = []
        events = {}
        options = {}
        if appliance.type in APPLIANCES_WITH_PROGRAMS:
            all_programs = await self.client.get_all_programs(appliance.ha_id)
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
                options = await self.get_options_definitions(current_program_key)
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

        commands = {
            command.key
            for command in (
                await self.client.get_available_commands(appliance.ha_id)
            ).commands
        }

        self.data.update(
            HomeConnectApplianceData(
                commands=commands,
                events=events,
                info=appliance,
                options=options,
                programs=programs,
                settings=settings,
                status=status,
            )
        )

    async def get_options_definitions(
        self, program_key: ProgramKey
    ) -> dict[OptionKey, ProgramDefinitionOption]:
        """Get options with constraints for appliance."""
        if program_key is ProgramKey.UNKNOWN:
            return {}
        try:
            return {
                option.key: option
                for option in (
                    await self.client.get_available_program(
                        self.data.info.ha_id, program_key=program_key
                    )
                ).options
                or []
            }
        except TooManyRequestsError:
            raise
        except HomeConnectError as error:
            _LOGGER.debug(
                "Error fetching options for %s: %s",
                self.data.info.ha_id,
                error,
            )
            return {}

    async def update_options(
        self, event_key: EventKey, program_key: ProgramKey
    ) -> None:
        """Update options for appliance."""
        options = self.data.options
        events = self.data.events
        options_to_notify = options.copy()
        options.clear()
        options.update(await self.get_options_definitions(program_key))

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
                EventKey(option_key),
                [],
            ):
                listener()

    def refreshed_too_often_recently(self) -> bool:
        """Check if the appliance data hasn't been refreshed too often recently."""

        now = self.hass.loop.time()

        execution_tracker = self._execution_tracker
        initial_len = len(execution_tracker)

        execution_tracker = self._execution_tracker = [
            timestamp
            for timestamp in execution_tracker
            if now - timestamp < MAX_EXECUTIONS_TIME_WINDOW
        ]

        execution_tracker.append(now)

        if len(execution_tracker) >= MAX_EXECUTIONS:
            if initial_len < MAX_EXECUTIONS:
                _LOGGER.warning(
                    'Too many connected/paired events for appliance "%s" '
                    "(%s times in less than %s minutes), updates have been disabled "
                    "and they will be enabled again whenever the connection stabilizes. "
                    "Consider trying to unplug the appliance "
                    "for a while to perform a soft reset",
                    self.data.info.name,
                    MAX_EXECUTIONS,
                    MAX_EXECUTIONS_TIME_WINDOW // 60,
                )
            return True
        if initial_len >= MAX_EXECUTIONS:
            _LOGGER.info(
                'Connected/paired events from the appliance "%s" have stabilized,'
                " updates have been re-enabled",
                self.data.info.name,
            )

        return False
