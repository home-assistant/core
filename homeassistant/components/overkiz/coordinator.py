"""Helpers to help coordinate updates."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from time import monotonic
from typing import TYPE_CHECKING, Any, overload, override

from aiohttp import ClientConnectorError, ServerDisconnectedError
from pyoverkiz.client import OverkizClient
from pyoverkiz.enums import (
    EventName,
    ExecutionState,
    FailureType,
    OverkizCommand,
    OverkizState,
    Protocol,
)
from pyoverkiz.exceptions import (
    BadCredentialsError,
    BaseOverkizError,
    InvalidEventListenerIdError,
    MaintenanceError,
    NotAuthenticatedError,
    ServiceUnavailableError,
    TooManyConcurrentRequestsError,
    TooManyRequestsError,
)
from pyoverkiz.models import (
    Action,
    Command,
    Device,
    DeviceEvent,
    DeviceRemovedEvent,
    DeviceStateChangedEvent,
    ExecutionRegisteredEvent,
    ExecutionStateChangedEvent,
    Place,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.decorator import Registry

if TYPE_CHECKING:
    from . import OverkizDataConfigEntry

from .const import (
    DOMAIN,
    IGNORED_OVERKIZ_DEVICES,
    LOGGER,
    MIN_WRITE_INTERVAL,
    UPDATE_INTERVAL,
)

# The commands that write the modes of a zone, as the key of their writes.
MODE_WRITE_NAMES: tuple[str, ...] = (
    str(OverkizCommand.SET_PASS_APC_HEATING_MODE),
    str(OverkizCommand.SET_PASS_APC_COOLING_MODE),
)

# Events are a discriminated union; each handler narrows to its own subtype.
EVENT_HANDLERS: Registry[
    str, Callable[[OverkizDataUpdateCoordinator, Any], Coroutine[Any, Any, None]]
] = Registry()


class OverkizDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching data from Overkiz platform."""

    config_entry: OverkizDataConfigEntry
    _default_update_interval: timedelta

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OverkizDataConfigEntry,
        logger: logging.Logger,
        *,
        client: OverkizClient,
        devices: list[Device],
        places: Place | None,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name="device events",
            update_interval=UPDATE_INTERVAL,
        )

        self.data = {}
        self.client = client
        self.devices: dict[str, Device] = {d.device_url: d for d in devices}
        self.executions: dict[str, list[dict[str, Any]]] = {}
        # Sequence number of the last execution that wrote each command of a
        # device, to only replay a command that nothing has replaced since.
        self.command_sequences: dict[tuple[str, str], int] = {}
        self.command_sequence = 0
        # Commands waiting for the running write of the same settings to end.
        self.pending_commands: dict[tuple[str, tuple[str, ...]], list[Command]] = {}
        # Writes that wait their turn, not yet registered as executions.
        self.writes_waiting: set[tuple[str, tuple[str, ...]]] = set()
        # Derogation state the last write that changed it left, as the states
        # only follow once the refreshes that come after it have run.
        self.derogation_writes: dict[str, tuple[str, float]] = {}
        # Mode of the program a zone was set to, until the device reports it.
        self.mode_writes: dict[str, tuple[str, float]] = {}
        self._write_lock = asyncio.Lock()
        # Once the config entry unloads, nothing deferred is sent any more.
        self._shutting_down = False
        self._last_write_at: float | None = None
        self.areas = self._places_to_area(places) if places else None
        self._default_update_interval = UPDATE_INTERVAL

        self.is_stateless = all(
            device.identifier.protocol in (Protocol.RTS, Protocol.INTERNAL)
            for device in devices
            if device.widget not in IGNORED_OVERKIZ_DEVICES
            and device.ui_class not in IGNORED_OVERKIZ_DEVICES
        )

    @overload
    async def async_execute_throttled(self, actions: list[Action]) -> str: ...

    @overload
    async def async_execute_throttled(
        self, actions: list[Action], still_wanted: Callable[[], bool]
    ) -> str | None: ...

    async def async_execute_throttled(
        self,
        actions: list[Action],
        still_wanted: Callable[[], bool] | None = None,
    ) -> str | None:
        """Execute actions, at least MIN_WRITE_INTERVAL after the previous write.

        With still_wanted, it is checked once the turn has come and the pause is
        over, right before the call, and nothing is sent if it is not true any
        more.
        """
        async with self._write_lock:
            if (
                self._last_write_at is not None
                and (
                    wait := MIN_WRITE_INTERVAL.total_seconds()
                    - (monotonic() - self._last_write_at)
                )
                > 0
            ):
                await asyncio.sleep(wait)

            if still_wanted is not None and not still_wanted():
                return None

            try:
                return await self.client.execute_action_group(
                    label="Home Assistant", actions=actions
                )
            finally:
                self._last_write_at = monotonic()

    def discard_pending_commands(
        self, device_url: str, command_names: set[str]
    ) -> None:
        """Forget the writes of these commands that wait for a device."""
        for key in [
            key
            for key in self.pending_commands
            if key[0] == device_url and command_names.intersection(key[1])
        ]:
            del self.pending_commands[key]

    @callback
    def async_create_write_task(self, target: Coroutine[Any, Any, None]) -> None:
        """Run a deferred write, canceled when the config entry is unloaded."""
        if self._shutting_down:
            target.close()
            return
        self.config_entry.async_create_background_task(
            self.hass, target, "overkiz deferred write"
        )

    @callback
    def async_send_pending_commands(self, key: tuple[str, tuple[str, ...]]) -> None:
        """Send what waits for a write of these settings, if anything."""
        if key in self.pending_commands:
            self.async_create_write_task(_send_pending_commands(self, key))

    @override
    async def async_shutdown(self) -> None:
        """Forget the writes still waiting, then shut down."""
        self._shutting_down = True
        self.pending_commands.clear()
        await super().async_shutdown()

    def is_execution_running(self, key: tuple[str, tuple[str, ...]]) -> bool:
        """Return whether a write of the same settings has been running lately."""
        return key in self.writes_waiting or any(
            record.get("key") == key and monotonic() - record["started"] < 60
            for records in self.executions.values()
            for record in records
        )

    def is_same_as_running(
        self, key: tuple[str, tuple[str, ...]], commands: list[Command]
    ) -> bool:
        """Return whether the last running write of these settings has these values."""
        running = [
            record
            for records in self.executions.values()
            for record in records
            if record.get("key") == key and monotonic() - record["started"] < 60
        ]
        if not running or not (sent := running[-1].get("commands")):
            return False

        def values(commands: list[Command]) -> list[tuple[str, tuple[Any, ...]]]:
            return [
                (str(command.name), tuple(command.parameters or ()))
                for command in commands
                if not str(command.name).startswith("refresh")
            ]

        return values(sent) == values(commands)

    def written_mode(self, device_url: str) -> str | None:
        """Return the mode a recent write set a device to, if not reported yet."""
        if (write := self.mode_writes.get(device_url)) is None:
            return None
        mode, written_at = write
        return mode if monotonic() - written_at < 120 else None

    def forget_mode_write(self, device_url: str, mode: str) -> None:
        """Forget a mode that was not applied, unless a newer request set another."""
        if (write := self.mode_writes.get(device_url)) is not None and write[0] == mode:
            del self.mode_writes[device_url]

    def is_mode_write_waiting(self, device_url: str) -> bool:
        """Return whether a write of the modes of a device waits or runs."""
        key = (device_url, MODE_WRITE_NAMES)
        return key in self.pending_commands or self.is_execution_running(key)

    def written_derogation(self, device_url: str) -> str | None:
        """Return the derogation a recent write left on a device, on or off."""
        if (write := self.derogation_writes.get(device_url)) is None:
            return None
        value, written_at = write
        return value if monotonic() - written_at < 120 else None

    @override
    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch Overkiz data via event listener."""
        try:
            events = await self.client.fetch_events()
        except (
            BadCredentialsError,
            NotAuthenticatedError,
            OAuth2TokenRequestReauthError,
        ) as exception:
            raise ConfigEntryAuthFailed("Invalid authentication.") from exception
        except OAuth2TokenRequestError as exception:
            raise UpdateFailed("Failed to refresh OAuth2 token.") from exception
        except TooManyConcurrentRequestsError as exception:
            raise UpdateFailed("Too many concurrent requests.") from exception
        except TooManyRequestsError as exception:
            raise UpdateFailed("Too many requests, try again later.") from exception
        except MaintenanceError as exception:
            raise UpdateFailed("Server is down for maintenance.") from exception
        except ServiceUnavailableError as exception:
            raise UpdateFailed("Server is unavailable.") from exception
        except InvalidEventListenerIdError as exception:
            raise UpdateFailed(exception) from exception
        except (TimeoutError, ClientConnectorError) as exception:
            LOGGER.debug("Failed to connect", exc_info=True)
            raise UpdateFailed("Failed to connect.") from exception
        except ServerDisconnectedError:
            self.executions = {}

            # During the relogin, similar exceptions can be thrown.
            try:
                await self.client.login()
                self.devices = await self._get_devices()
            except (BadCredentialsError, NotAuthenticatedError) as exception:
                raise ConfigEntryAuthFailed("Invalid authentication.") from exception
            except TooManyRequestsError as exception:
                raise UpdateFailed("Too many requests, try again later.") from exception

            # The states have just been fetched again: the derogation they
            # report replaces the one a write left.
            self.derogation_writes.clear()
            self.mode_writes.clear()

            # What waited for a running write, which is forgotten now, is sent.
            for key in list(self.pending_commands):
                self.async_create_write_task(_send_pending_commands(self, key))

            return self.devices

        for event in events:
            LOGGER.debug(event)

            if event_handler := EVENT_HANDLERS.get(event.name):
                await event_handler(self, event)

        # Restore the default update interval if no executions are pending
        if not self.executions:
            self.update_interval = self._default_update_interval

        return self.devices

    async def _get_devices(self) -> dict[str, Device]:
        """Fetch devices."""
        LOGGER.debug("Fetching all devices and state via /setup/devices")
        return {d.device_url: d for d in await self.client.get_devices(refresh=True)}

    def _places_to_area(self, place: Place) -> dict[str, str]:
        """Convert places with sub_places to a flat dictionary [placeoid, label])."""
        areas = {}
        if isinstance(place, Place):
            areas[place.oid] = place.label

        if isinstance(place.sub_places, list):
            for sub_place in place.sub_places:
                areas.update(self._places_to_area(sub_place))

        return areas

    def set_update_interval(self, update_interval: timedelta) -> None:
        """Set the update interval and store this value."""
        self.update_interval = update_interval
        self._default_update_interval = update_interval


@EVENT_HANDLERS.register(EventName.DEVICE_AVAILABLE)
async def on_device_available(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceEvent
) -> None:
    """Handle device available event."""
    if event.device_url in coordinator.devices:
        coordinator.devices[event.device_url].available = True


@EVENT_HANDLERS.register(EventName.DEVICE_UNAVAILABLE)
@EVENT_HANDLERS.register(EventName.DEVICE_DISABLED)
async def on_device_unavailable_disabled(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceEvent
) -> None:
    """Handle device unavailable / disabled event."""
    if event.device_url in coordinator.devices:
        coordinator.devices[event.device_url].available = False


@EVENT_HANDLERS.register(EventName.DEVICE_CREATED)
@EVENT_HANDLERS.register(EventName.DEVICE_UPDATED)
async def on_device_created_updated(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceEvent
) -> None:
    """Handle device unavailable / disabled event."""
    coordinator.hass.async_create_task(
        coordinator.hass.config_entries.async_reload(coordinator.config_entry.entry_id)
    )


@EVENT_HANDLERS.register(EventName.DEVICE_STATE_CHANGED)
async def on_device_state_changed(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceStateChangedEvent
) -> None:
    """Handle device state changed event."""
    if event.device_url not in coordinator.devices:
        return

    for state in event.device_states:
        device = coordinator.devices[event.device_url]
        device.states[state.name] = state

        # The derogation and the mode the device reports replace the ones a
        # write left.
        if state.name == OverkizState.CORE_DEROGATION_ON_OFF:
            coordinator.derogation_writes.pop(event.device_url, None)
        elif state.name in (
            OverkizState.IO_PASS_APC_HEATING_MODE,
            OverkizState.IO_PASS_APC_COOLING_MODE,
        ) and not coordinator.is_mode_write_waiting(event.device_url):
            # A mode written later, still on its way, is the one that applies.
            coordinator.mode_writes.pop(event.device_url, None)


@EVENT_HANDLERS.register(EventName.DEVICE_REMOVED)
async def on_device_removed(
    coordinator: OverkizDataUpdateCoordinator, event: DeviceRemovedEvent
) -> None:
    """Handle device removed event."""
    base_device_url = event.device_url.split("#")[0]
    registry = dr.async_get(coordinator.hass)

    if registered_device := registry.async_get_device_by_identifier(
        (DOMAIN, base_device_url), coordinator.config_entry.entry_id
    ):
        registry.async_remove_device(registered_device.id)

    if event.device_url in coordinator.devices:
        del coordinator.devices[event.device_url]


@EVENT_HANDLERS.register(EventName.EXECUTION_REGISTERED)
async def on_execution_registered(
    coordinator: OverkizDataUpdateCoordinator, event: ExecutionRegisteredEvent
) -> None:
    """Handle execution registered event."""
    if event.exec_id not in coordinator.executions:
        coordinator.executions[event.exec_id] = []

    if not coordinator.is_stateless:
        coordinator.update_interval = timedelta(seconds=1)


@EVENT_HANDLERS.register(EventName.EXECUTION_STATE_CHANGED)
async def on_execution_state_changed(
    coordinator: OverkizDataUpdateCoordinator, event: ExecutionStateChangedEvent
) -> None:
    """Handle execution changed event."""
    if event.new_state not in (ExecutionState.COMPLETED, ExecutionState.FAILED):
        return

    # The execution is over: forget it before anything is started in reaction.
    records = coordinator.executions.pop(event.exec_id, None)

    replaying = False
    if event.new_state == ExecutionState.FAILED:
        replaying = _report_failed_execution(coordinator, event, records)

    if records is None:
        return

    _track_derogation_writes(coordinator, records, event, replaying=replaying)

    # A setting that went through ends the failure reported for the device.
    if event.new_state == ExecutionState.COMPLETED:
        for record in records:
            if _written_commands(record):
                ir.async_delete_issue(
                    coordinator.hass,
                    DOMAIN,
                    f"execution_failed_{record['device_url']}",
                )

    # A command lost and replayed ends with the replay, which then sends what
    # has been waiting.
    if not replaying:
        for record in records:
            if (key := record.get("key")) is not None:
                coordinator.async_create_write_task(
                    _send_pending_commands(coordinator, key)
                )


def _written_commands(record: dict[str, Any]) -> list[Command]:
    """Return the commands of an execution that write a setting."""
    return [
        command
        for command in record.get("commands") or ()
        if not str(command.name).startswith("refresh")
    ]


def _applied_commands(
    records: list[dict[str, Any]], event: ExecutionStateChangedEvent
) -> list[list[Command]] | None:
    """Return the commands of each record that the device applied.

    The commands of an execution run in order and stop at the first that fails:
    those before it are applied. None when a failure doesn't tell which one.
    """
    if event.new_state == ExecutionState.COMPLETED:
        return [record.get("commands") or [] for record in records]

    ranks = [
        command["rank"]
        for command in event.failed_commands or ()
        if isinstance(command, dict) and isinstance(command.get("rank"), int)
    ]
    if len(records) != 1 or not ranks:
        return None

    return [(records[0].get("commands") or [])[: min(ranks)]]


def _track_derogation_writes(
    coordinator: OverkizDataUpdateCoordinator,
    records: list[dict[str, Any]],
    event: ExecutionStateChangedEvent,
    *,
    replaying: bool = False,
) -> None:
    """Remember the derogation a finished write left on its device."""
    applied = _applied_commands(records, event)

    for index, record in enumerate(records):
        device_url = record["device_url"]
        applied_names = (
            None
            if applied is None
            else {str(command.name) for command in applied[index]}
        )

        # A mode that was not applied to both sides is not the one the device
        # will report. A refresh that fails after it leaves it applied, and a
        # replay may still apply it.
        modes = [
            command
            for command in _written_commands(record)
            if str(command.name) in MODE_WRITE_NAMES
        ]
        if (
            modes
            and not replaying
            and (
                applied_names is None
                or any(str(command.name) not in applied_names for command in modes)
            )
            and modes[0].parameters
        ):
            coordinator.forget_mode_write(device_url, str(modes[0].parameters[0]))

        for command in _written_commands(record):
            if command.name != OverkizCommand.SET_DEROGATION_ON_OFF_STATE:
                continue
            if (
                applied_names is not None
                and OverkizCommand.SET_DEROGATION_ON_OFF_STATE in applied_names
                and command.parameters
            ):
                coordinator.derogation_writes[device_url] = (
                    str(command.parameters[0]),
                    monotonic(),
                )
            else:
                coordinator.derogation_writes.pop(device_url, None)


def _create_failure_issue(
    coordinator: OverkizDataUpdateCoordinator, device_url: str, error: str
) -> None:
    """Tell the user that a command was not applied to a device."""
    device = coordinator.devices.get(device_url)
    ir.async_create_issue(
        coordinator.hass,
        DOMAIN,
        f"execution_failed_{device_url}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="execution_failed",
        translation_placeholders={
            "device": device.label if device is not None else device_url,
            "error": error,
        },
    )


async def _send_pending_commands(
    coordinator: OverkizDataUpdateCoordinator,
    key: tuple[str, tuple[str, ...]],
) -> None:
    """Send the commands that waited for the write of the same settings."""
    if (commands := coordinator.pending_commands.pop(key, None)) is None:
        return

    # Local import: the executor imports this module.
    from .executor import OverkizExecutor  # noqa: PLC0415

    try:
        await OverkizExecutor(key[0], coordinator).async_execute_commands(
            commands, coalesce=True
        )
    except HomeAssistantError:
        # The service call that gave these commands returned long ago and no
        # execution will report their failure.
        LOGGER.warning("Sending the waiting Overkiz commands failed", exc_info=True)
        _create_failure_issue(coordinator, key[0], "REQUEST_FAILED")
        for command in commands:
            if (
                command.name == OverkizCommand.SET_PASS_APC_HEATING_MODE
                and command.parameters
            ):
                coordinator.forget_mode_write(key[0], str(command.parameters[0]))


def _report_failed_execution(
    coordinator: OverkizDataUpdateCoordinator,
    event: ExecutionStateChangedEvent,
    commands: list[dict[str, Any]] | None,
    *,
    replayed: bool = False,
) -> bool:
    """Tell the user that a command did not reach its device.

    The service call has already returned by the time the server reports a
    failure, so the command would otherwise fail silently. Return whether the
    command is replayed instead.
    """
    # Executions started from the app or a remote are registered without any
    # command, and a failure code the library doesn't know describes nothing
    # the user can act on.
    if not commands or event.failure_type_code in (
        None,
        FailureType.UNKNOWN,
        FailureType.NO_FAILURE,
    ):
        LOGGER.debug(
            "Overkiz execution %s failed (%s)", event.exec_id, event.failure_type_code
        )
        return False

    # A refresh that fails (a transport error, for example) leaves the setting
    # applied and only delays the new states: nothing for the user to act on.
    failed_names = _failed_command_names(commands, event)
    if failed_names is None:
        # Without the failed commands, only a device that is down, or executions
        # merged under one id that all wrote a setting, are reported. A refresh
        # alone leaves no setting unapplied.
        actionable = (
            event.failure_type_code == FailureType.PEER_DOWN
            and any(_written_commands(record) for record in commands)
        ) or (
            len(commands) > 1 and all(_written_commands(record) for record in commands)
        )
    else:
        actionable = any(not name.startswith("refresh") for name in failed_names)

    if not actionable:
        LOGGER.debug(
            "Overkiz execution %s failed (%s): %s",
            event.exec_id,
            event.failure_type_code,
            event.failed_commands,
        )
        return False

    # The link between the box and the device drops a command now and then,
    # and a second attempt goes through: replay once, for the writes that
    # asked for it, before bothering the user.
    if (
        not replayed
        and event.failure_type_code == FailureType.DATA_TRANSPORT_SERVICE_ERROR
        and len(commands) == 1
        and commands[0].get("replay_allowed")
    ):
        LOGGER.debug("Replaying Overkiz execution %s", event.exec_id)
        coordinator.async_create_write_task(
            _replay_failed_execution(coordinator, commands[0], event)
        )
        return True

    for device_url in {record["device_url"] for record in commands}:
        _create_failure_issue(coordinator, device_url, event.failure_type_code.name)
    return False


async def _replay_failed_execution(
    coordinator: OverkizDataUpdateCoordinator,
    record: dict[str, Any],
    event: ExecutionStateChangedEvent,
) -> None:
    """Run again a command the device did not receive, once."""
    device_url = record["device_url"]
    sent: list[Command] = record["commands"]
    sequence: int = record["sequence"]

    # A newer value of a setting must not be overwritten by an older one: this
    # is checked when the write is about to be sent, after the wait for its turn.
    def still_wanted() -> bool:
        return all(
            coordinator.command_sequences.get((device_url, command.name)) == sequence
            for command in _written_commands(record)
        )

    # Until the replay runs, a new value of the setting waits behind it, as it
    # would behind the write that failed.
    key = record.get("key")
    if key is not None:
        coordinator.writes_waiting.add(key)

    try:
        exec_id = await coordinator.async_execute_throttled(
            [Action(device_url=device_url, commands=sent)], still_wanted
        )
    except (
        BaseOverkizError,
        TimeoutError,
        ClientConnectorError,
        ServerDisconnectedError,
    ):
        LOGGER.warning("Replay of the Overkiz command failed", exc_info=True)
        _report_failed_execution(coordinator, event, [record], replayed=True)
        exec_id = None
    else:
        if exec_id is None:
            LOGGER.debug(
                "Not replaying Overkiz execution %s: superseded", event.exec_id
            )
        else:
            # The replay is not replayed in turn.
            coordinator.executions.setdefault(exec_id, []).append(
                {
                    "device_url": device_url,
                    "command_name": record["command_name"],
                    "command_names": record["command_names"],
                    "commands": sent,
                    "key": key,
                    "started": monotonic(),
                }
            )
    finally:
        if key is not None:
            coordinator.writes_waiting.discard(key)

    # As after any write: the events of the replay are polled at once, and
    # quickly until it ends, instead of at the slower idle interval.
    if exec_id is not None:
        await coordinator.async_refresh()

    if exec_id is None:
        # Without a replay, the mode it would have written is not applied.
        for command in _written_commands(record):
            if (
                command.name == OverkizCommand.SET_PASS_APC_HEATING_MODE
                and command.parameters
            ):
                coordinator.forget_mode_write(device_url, str(command.parameters[0]))

        # Without a replay running, nothing will send what waits once it ends.
        if key is not None:
            await _send_pending_commands(coordinator, key)


def _failed_command_names(
    commands: list[dict[str, Any]], event: ExecutionStateChangedEvent
) -> list[str] | None:
    """Return the names of the commands that failed, if the event says which."""
    if len(commands) != 1 or not event.failed_commands:
        return None

    names = commands[0].get("command_names", [])
    ranks = [
        command["rank"]
        for command in event.failed_commands
        if isinstance(command, dict) and isinstance(command.get("rank"), int)
    ]

    if not ranks or any(rank >= len(names) for rank in ranks):
        return None

    return [names[rank] for rank in ranks]
