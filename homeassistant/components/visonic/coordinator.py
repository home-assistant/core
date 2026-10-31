"""Coordinate Visonic state through a direct or cloud connection."""

import asyncio
from collections.abc import Callable, Coroutine, Generator
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import aiohttp
from pyvisonic import ConnectionType, VisonicClientSettings

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.persistent_notification import (
    helpers as persistent_notification,
)
from homeassistant.const import (
    CONF_CODE,
    CONF_DEVICE,
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud import VisonicCloudConnection, VisonicCloudSettings
from .connection import (
    VisonicConnection,
    VisonicConnectionCallbacks,
    VisonicConnectionOptions,
    VisonicPanelMetadata,
)
from .const import (
    CONF_ARM_CODE_AUTO,
    CONF_ARM_HOME_ENABLED,
    CONF_CLOUD_APP_ID,
    CONF_DEVICE_BAUD,
    CONF_DOWNLOAD_CODE,
    CONF_ENABLE_REMOTE_ARM,
    CONF_ENABLE_REMOTE_DISARM,
    CONF_EPROM_ATTRIBUTES,
    CONF_PANEL_SERIAL,
    CONF_RETRY_CONNECTION_COUNT,
    CONF_RETRY_CONNECTION_DELAY,
    CONF_USER_CODE_SLOT,
    DEFAULT_CLOUD_SCAN_INTERVAL,
    DEFAULT_DIRECT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    PANEL_ATTRIBUTE_NAME,
    TEXT_DISCONNECTION_COUNT,
    TEXT_PANEL_MODEL,
)
from .direct import VisonicDirectConnection
from .exceptions import VisonicAuthException, VisonicException
from .identity import redact_panel_identification
from .utils import capitalize, get_alarm_panel_unique_ident, to_bool
from .visonic_data_types import VisonicConfigEntry, VisonicCoordinatorData
from .visonic_entity_types import AlarmPanelData
from .visonic_types import (
    AlarmCommandStatus,
    AlarmPanelCommand,
    AlarmPanelStatus,
    CommandResult,
    DeviceType,
    PanelStateData,
)

# Map the alarm panel states across to the Home Assistant states
PANEL_TO_HA_STATUS_MAP: dict[AlarmPanelStatus, AlarmControlPanelState | None] = {
    AlarmPanelStatus.UNKNOWN: None,
    AlarmPanelStatus.TRIGGERED: AlarmControlPanelState.TRIGGERED,
    AlarmPanelStatus.DISARMED: AlarmControlPanelState.DISARMED,
    AlarmPanelStatus.ARMING_HOME: AlarmControlPanelState.ARMING,
    AlarmPanelStatus.ARMING_AWAY: AlarmControlPanelState.ARMING,
    AlarmPanelStatus.ENTRY_DELAY: AlarmControlPanelState.PENDING,
    AlarmPanelStatus.ENTRY_DELAY_INSTANT: AlarmControlPanelState.PENDING,
    AlarmPanelStatus.ARMED_HOME: AlarmControlPanelState.ARMED_HOME,
    AlarmPanelStatus.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    AlarmPanelStatus.ARMED_HOME_BYPASS: AlarmControlPanelState.ARMED_HOME,
    AlarmPanelStatus.ARMED_AWAY_BYPASS: AlarmControlPanelState.ARMED_AWAY,
    AlarmPanelStatus.ARMED_HOME_INSTANT: AlarmControlPanelState.ARMED_HOME,
    AlarmPanelStatus.ARMED_AWAY_INSTANT: AlarmControlPanelState.ARMED_AWAY,
    AlarmPanelStatus.USER_TEST: None,
    AlarmPanelStatus.DOWNLOADING: None,
    AlarmPanelStatus.INSTALLER: None,
}

MESSAGE_REASON_DICT: dict[AlarmCommandStatus, type[HomeAssistantError]] = {
    AlarmCommandStatus.FAIL_DOWNLOAD_IN_PROGRESS: HomeAssistantError,
    AlarmCommandStatus.FAIL_INVALID_CODE: ServiceValidationError,
    AlarmCommandStatus.FAIL_USER_CONFIG_PREVENTED: ServiceValidationError,
    AlarmCommandStatus.FAIL_RECOVERY_IN_PROGRESS: HomeAssistantError,
    AlarmCommandStatus.FAIL_INVALID_STATE: ServiceValidationError,
    AlarmCommandStatus.FAIL_INVALID_RETURN: HomeAssistantError,
    AlarmCommandStatus.FAIL_INVALID_PROCESS_TOKEN: HomeAssistantError,
    AlarmCommandStatus.FAIL_SWITCH_PROBLEM: HomeAssistantError,
    AlarmCommandStatus.FAIL_PANEL_CONFIG_PREVENTED: ServiceValidationError,
    AlarmCommandStatus.FAIL_ENTITY_INCORRECT: HomeAssistantError,
    AlarmCommandStatus.FAIL_PANEL_NO_CONNECTION: HomeAssistantError,
    AlarmCommandStatus.FAIL_ABSTRACT_CLASS_NOT_IMPLEMENTED: HomeAssistantError,
}


class VisonicCoordinator(DataUpdateCoordinator[VisonicCoordinatorData]):
    """Manage shared Home Assistant state using a direct or cloud connection."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: VisonicConfigEntry,
        panel_id: int | str,
        update_interval: int | None = None,
    ) -> None:
        """Initialize the coordinator and its connection helper."""
        device_type = DeviceType(entry.data[CONF_TYPE])
        if update_interval is None:
            update_interval = (
                DEFAULT_CLOUD_SCAN_INTERVAL
                if device_type == DeviceType.CLOUD
                else DEFAULT_DIRECT_SCAN_INTERVAL
            )
        request_refresh_debouncer: Debouncer[Coroutine[Any, Any, None]] = Debouncer(
            hass=hass,
            logger=LOGGER,
            cooldown=update_interval,
            immediate=True,
        )
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"{capitalize(DOMAIN)} panel {panel_id}"
            if isinstance(panel_id, int)
            else f"{capitalize(DOMAIN)} panel",
            config_entry=entry,
            update_interval=timedelta(seconds=update_interval),
            update_method=self.my_update_data,
            request_refresh_debouncer=request_refresh_debouncer,  # The function gets added inside
        )

        self.panel_id = panel_id
        self._coordinator_update_timer: Callable[[], None] | None = None
        self._last_my_state: AlarmControlPanelState | None = None
        self._stopping = False
        self._refresh_tasks: set[asyncio.Task[Any]] = set()

        self._command_lock = asyncio.Lock()
        self._alarm_setup_lock = asyncio.Lock()
        self._created_alarm_panel = False
        self._device_type = device_type
        self._entry_data = dict(entry.data)
        self._cloud_settings: VisonicCloudSettings | None = None
        callbacks = VisonicConnectionCallbacks(
            state_changed=self.state_changed_callback,
            panel_ready=self._handle_panel_ready,
            panel_metadata_changed=self._handle_panel_metadata,
            baud_changed=self._handle_baud_change,
            app_id_changed=self._handle_app_id_change,
            recovery_failed=self._handle_recovery_failed,
        )
        options = self._connection_options(entry)
        self.connection: VisonicConnection
        if device_type == DeviceType.CLOUD:
            self._cloud_settings = VisonicCloudSettings(
                hostname=entry.data.get(CONF_EXTERNAL_URL, ""),
                email=entry.data.get(CONF_EMAIL, ""),
                password=entry.data.get(CONF_PASSWORD, ""),
                code=entry.data.get(CONF_CODE, ""),
                panel_serial=entry.data.get(CONF_PANEL_SERIAL, ""),
                panel_id=panel_id if isinstance(panel_id, int) else 0,
                panel_name=entry.title,
                update_interval=update_interval,
                app_id=entry.data.get(CONF_CLOUD_APP_ID),
            )
            self.connection = VisonicCloudConnection(
                self._cloud_settings, options, callbacks, async_get_clientsession(hass)
            )
        else:
            settings = VisonicClientSettings(
                connection_type=ConnectionType(entry.data[CONF_TYPE]),
                host=entry.data.get(CONF_HOST, "127.0.0.1"),
                port=int(entry.data.get(CONF_PORT, 30000)),
                path=entry.data.get(CONF_DEVICE, "/dev/ttyUSB0"),
                baud=int(entry.data.get(CONF_DEVICE_BAUD, 9600)),
                force_standard_mode=False,
                download_code=entry.data.get(CONF_DOWNLOAD_CODE, ""),
                user_code_slot=int(entry.data.get(CONF_USER_CODE_SLOT, 1)) - 1,
                retry_count=options.retry_count,
                retry_delay=options.retry_delay,
                panel_id=panel_id if isinstance(panel_id, int) else 0,
            )
            self.connection = VisonicDirectConnection(settings, options, callbacks)
        entry.async_on_unload(entry.add_update_listener(self._async_entry_updated))

    @staticmethod
    def _connection_options(entry: VisonicConfigEntry) -> VisonicConnectionOptions:
        return VisonicConnectionOptions(
            enable_remote_arm=to_bool(entry.options.get(CONF_ENABLE_REMOTE_ARM, False)),
            enable_remote_disarm=to_bool(
                entry.options.get(CONF_ENABLE_REMOTE_DISARM, False)
            ),
            arm_home_enabled=to_bool(entry.options.get(CONF_ARM_HOME_ENABLED, True)),
            arm_without_usercode=to_bool(entry.options.get(CONF_ARM_CODE_AUTO, False)),
            eprom_attributes=to_bool(entry.options.get(CONF_EPROM_ATTRIBUTES, False)),
            retry_count=int(entry.options.get(CONF_RETRY_CONNECTION_COUNT, 1)),
            retry_delay=float(entry.options.get(CONF_RETRY_CONNECTION_DELAY, 90)),
        )

    async def _async_entry_updated(
        self, _hass: HomeAssistant, entry: VisonicConfigEntry
    ) -> None:
        if entry.data != self._entry_data:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return
        options = self._connection_options(entry)
        if options == self.connection.options:
            return
        self.connection.update_options(options)
        await self.async_request_refresh()

    @callback
    def _handle_recovery_failed(self) -> None:
        """Stop integration activity and show the terminal recovery error."""
        persistent_notification.async_create(
            self.hass,
            "Visonic flood recovery failed. "
            "The integration has stopped communicating. Reload the integration to reconnect.",
            title=f"Visonic panel {self.panel_id}: recovery failed",
            notification_id=f"visonic_recovery_failed_{self.panel_id}",
        )
        self.hass.async_create_task(
            self.async_panel_stop(),
            name=f"Stop Visonic {self.panel_id} after recovery failure",
        )

    @callback
    def _handle_panel_ready(self) -> None:
        if self._stopping:
            return
        persistent_notification.async_dismiss(
            self.hass, f"visonic_recovery_failed_{self.panel_id}"
        )
        if cast(VisonicCoordinatorData | None, self.data) is None:
            return
        if TYPE_CHECKING:
            assert self.config_entry is not None
        self.config_entry.async_create_task(
            self.hass,
            self.async_setup_alarm_panel(),
            name=f"Set up Visonic panel {self.panel_id}",
        )

    @callback
    def _handle_panel_metadata(self, metadata: VisonicPanelMetadata) -> None:
        if TYPE_CHECKING:
            assert self.config_entry is not None
        data = dict(self.config_entry.data) | {TEXT_PANEL_MODEL: metadata.model}
        if metadata.serial is not None:
            data[CONF_PANEL_SERIAL] = metadata.serial
            self._entry_data = data
            title = f"Panel {self.panel_id} ({metadata.model or 'Unknown model'})"
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data, title=title
            )
            if self._cloud_settings is not None:
                self._cloud_settings.panel_name = title
        else:
            if self._device_type != DeviceType.CLOUD:
                data.pop(CONF_PANEL_SERIAL, None)
            self._entry_data = data
            title = (
                f"Panel {self.panel_id} ({metadata.model or 'Unknown model'})"
                if isinstance(self.panel_id, int)
                else f"Visonic {metadata.model or 'panel'}"
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data, title=title
            )
        if self._device_type != DeviceType.CLOUD:
            self.set_alarm_device_information(
                metadata.model if metadata.model is not None else UNDEFINED
            )

    @callback
    def _handle_baud_change(self, baud: int) -> None:
        if TYPE_CHECKING:
            assert self.config_entry is not None
        self._entry_data = dict(self.config_entry.data) | {CONF_DEVICE_BAUD: baud}
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self._entry_data,
        )

    @callback
    def _handle_app_id_change(self, app_id: str) -> None:
        if TYPE_CHECKING:
            assert self.config_entry is not None
        if self.config_entry.data.get(CONF_CLOUD_APP_ID) != app_id:
            self._entry_data = dict(self.config_entry.data) | {
                CONF_CLOUD_APP_ID: app_id
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self._entry_data,
            )

    @callback
    def set_alarm_device_information(
        self, model: str | UndefinedType = UNDEFINED
    ) -> None:
        """Register or update the alarm panel device."""
        if TYPE_CHECKING:
            assert self.config_entry is not None
        device_registry = dr.async_get(self.hass)
        panel_unique_id = get_alarm_panel_unique_ident(self.panel_id)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, panel_unique_id)},
            name=panel_unique_id
            if isinstance(self.panel_id, int)
            else self.config_entry.title,
            manufacturer=MANUFACTURER,
            model=model,
        )

    @callback
    def create_alarm_panel(self) -> AlarmPanelData:
        """Announce the panel to the alarm platform."""
        if TYPE_CHECKING:
            assert self.config_entry is not None
        alarm_data = AlarmPanelData(get_alarm_panel_unique_ident(self.panel_id))
        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_{self.config_entry.entry_id}_add_{Platform.ALARM_CONTROL_PANEL}",
            alarm_data,
        )
        return alarm_data

    async def async_setup_alarm_panel(self) -> None:
        """Announce alarm entities once when panel setup completes."""
        async with self._alarm_setup_lock:
            if not self._stopping and not self._created_alarm_panel:
                self._created_alarm_panel = True
                self.create_alarm_panel()

    def start_coordinator_update_timer(self, delay: float) -> None:
        """Update timer for sequential update control."""
        if self._stopping:
            return
        if self._coordinator_update_timer is not None:
            self._coordinator_update_timer()
            self._coordinator_update_timer = None
        if delay <= 0.0:
            if TYPE_CHECKING:
                assert self.config_entry is not None
            self.config_entry.async_create_task(
                self.hass,
                self.async_state_changed_callback(),
                name=f"Update Visonic panel {self.panel_id}",
            )
            return
        self._coordinator_update_timer = async_call_later(
            self.hass,
            delay,
            self._coordinator_update_timer_callback,
        )

    @callback
    def _coordinator_update_timer_callback(self, _now: datetime) -> None:
        self._coordinator_update_timer = None
        self.start_coordinator_update_timer(-1.0)  # trigger immediate update

    @contextmanager
    def _track_refresh(self) -> Generator[None]:
        """Keep running refreshes available for cancellation during shutdown."""
        if self._stopping:
            raise asyncio.CancelledError
        task = asyncio.current_task()
        if TYPE_CHECKING:
            assert task is not None
        self._refresh_tasks.add(task)
        try:
            yield
        finally:
            self._refresh_tasks.discard(task)

    @callback
    def _async_handle_authentication_failure(self, err: VisonicAuthException) -> None:
        """Publish lost authentication and request updated credentials."""
        if self._stopping:
            return
        if TYPE_CHECKING:
            assert self.config_entry is not None
        self.async_set_update_error(
            ConfigEntryAuthFailed(
                redact_panel_identification(
                    str(err), self.config_entry.data.get(CONF_PANEL_SERIAL)
                )
            )
        )
        self.config_entry.async_start_reauth_if_available(self.hass)

    async def async_state_changed_callback(self) -> None:
        """Publish pushed state and report availability transitions."""
        with self._track_refresh():
            try:
                data = await self.create_state_snapshot()
            except VisonicAuthException as err:
                self._async_handle_authentication_failure(err)
                return
            except UpdateFailed as err:
                if self.data is not None:
                    self.async_set_update_error(err)
                return

            if not self.last_update_success:
                LOGGER.info("Fetching %s data recovered", self.name)

            self.async_set_updated_data(data)

    @callback
    def state_changed_callback(self, delay: float = 0.2) -> None:
        """Client calls this when the panel data has changed."""
        # If a single message from the panel contains multiple updates (i.e to multiple sensors, switches etc)
        #   meaning that this function gets called multiple times in quick succession
        #   then we should delay the update until they've all been processed.
        #   This cuts down on the number of coordinator update calls to the listeners
        self.start_coordinator_update_timer(delay)

    async def my_update_data(self) -> VisonicCoordinatorData:
        """Update Data."""
        with self._track_refresh():
            if self._coordinator_update_timer is not None:
                # If a timer is in progress to perform a data update then cancel it
                self._coordinator_update_timer()
                self._coordinator_update_timer = None
            try:
                snapshot = await self.create_state_snapshot()
            except VisonicAuthException as err:
                if TYPE_CHECKING:
                    assert self.config_entry is not None
                raise ConfigEntryAuthFailed(
                    redact_panel_identification(
                        str(err), self.config_entry.data.get(CONF_PANEL_SERIAL)
                    )
                ) from None
            except UpdateFailed:
                raise
            except Exception as err:  # noqa: BLE001 - Do not expose raw panel errors.
                raise UpdateFailed(
                    f"Panel update failed ({type(err).__name__})"
                ) from None
            if (
                self._device_type == DeviceType.CLOUD
                and snapshot.connected
                and not self._created_alarm_panel
            ):
                # Entity setup needs data before the refresh publishes it.
                self.data = snapshot
                if TYPE_CHECKING:
                    assert self.config_entry is not None
                model = self.config_entry.data.get(TEXT_PANEL_MODEL)
                self.set_alarm_device_information(
                    model if model is not None else UNDEFINED
                )
                await self.async_setup_alarm_panel()
            return snapshot

    async def create_state_snapshot(self) -> VisonicCoordinatorData:
        """Read an available whole-panel snapshot."""
        try:
            snapshot = await self.connection.create_state_snapshot()
        except VisonicAuthException, UpdateFailed:
            raise
        except Exception as err:  # noqa: BLE001 - Do not expose raw panel errors.
            raise UpdateFailed(f"Panel update failed ({type(err).__name__})") from None
        if not snapshot.connected:
            raise UpdateFailed("Panel is disconnected")
        return snapshot

    def ive_been_created(self) -> None:
        """Refresh pushed state when the direct alarm entity is created."""
        if self._device_type == DeviceType.CLOUD:
            return
        try:
            self.state_changed_callback()
        except Exception as err:  # noqa: BLE001 - Do not expose raw panel errors.
            raise VisonicException(
                "Client not created properly", code=300, original_exception=err
            ) from None

    async def async_panel_connect(self) -> bool:
        """Connect through the selected backend."""
        connected = await self.connection.async_panel_connect()
        if connected:
            await self.async_config_entry_first_refresh()
            if not self.data.connected:
                raise ConfigEntryNotReady("No initial panel state available")
            self.set_alarm_device_information()
            await self.async_setup_alarm_panel()
        return connected

    async def async_panel_stop(self) -> None:
        """Cancel pending updates, publish stopped state and close the connection."""
        self._stopping = True
        if self._coordinator_update_timer is not None:
            self._coordinator_update_timer()
            self._coordinator_update_timer = None
        await self.async_shutdown()
        refresh_tasks = tuple(self._refresh_tasks)
        for task in refresh_tasks:
            task.cancel()
        await asyncio.gather(*refresh_tasks, return_exceptions=True)
        self.async_set_updated_data(
            VisonicCoordinatorData(connected=False, mode="stopped")
        )
        async with self._command_lock:
            await self.connection.async_panel_stop()

    # the return value indicates whether any sensors needed to be bypassed
    async def send_command(
        self, command: AlarmPanelCommand, code: str | None
    ) -> CommandResult:
        """Send a whole-panel command through the selected connection."""
        async with self._command_lock:
            if self._stopping:
                return CommandResult(AlarmCommandStatus.FAIL_PANEL_NO_CONNECTION)
            try:
                return await self.connection.send_command(command, code)
            except VisonicAuthException as err:
                self._async_handle_authentication_failure(err)
                raise
            except TimeoutError, OSError, aiohttp.ClientError:
                raise HomeAssistantError(
                    f"Unable to communicate with Visonic panel {self.panel_id}"
                ) from None

    def get_panel_state(self) -> PanelStateData:
        """Return the whole-panel state for the alarm entity."""
        data = self.data
        if not data or not data.connected:
            return PanelStateData()
        alarm_state: AlarmControlPanelState | None
        if data.siren_active:
            alarm_state = AlarmControlPanelState.TRIGGERED
        elif data.armcode == AlarmPanelStatus.DOWNLOADING:
            alarm_state = self._last_my_state
        else:
            alarm_state = PANEL_TO_HA_STATUS_MAP.get(data.armcode)
        self._last_my_state = alarm_state
        attributes = deepcopy(data.panelstate.as_dict()) if data.panelstate else {}
        attributes.update(data.statusdict)
        attributes[TEXT_DISCONNECTION_COUNT] = data.disconnection_count
        attributes["state"] = data.armcode.name.lower()
        attributes[PANEL_ATTRIBUTE_NAME] = str(self.panel_id)
        attributes = {
            key: "none" if value is None else value for key, value in attributes.items()
        }
        return PanelStateData(
            connected=True,
            achieved_powerlink=data.achieved_powerlink,
            alarm_state=alarm_state,
            attributes=attributes,
        )

    def process_command_result(self, cr: CommandResult | None) -> None:
        """Process the alarm command result and if not Success take appropriate action."""
        # This is generic across Direct and Cloud connections
        if cr is None:
            return

        if cr.status != AlarmCommandStatus.SUCCESS:
            raise MESSAGE_REASON_DICT[cr.status](
                translation_domain=DOMAIN,
                translation_key=cr.status.name.lower(),
                translation_placeholders={"panel_id": str(self.panel_id)},
            )
