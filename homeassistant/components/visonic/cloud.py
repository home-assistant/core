"""Cloud connection helper for the Visonic coordinator."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, override
import uuid

import aiohttp
from pyvisonicalarm.alarm import AlarmSystem
from pyvisonicalarm.classes import Partition
from pyvisonicalarm.core import API
from pyvisonicalarm.devices import Device, PanelDevice
from pyvisonicalarm.exceptions import (
    Error,
    SessionTokenError,
    UnauthorizedError,
    UserAuthRequiredError,
)

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from .connection import (
    VisonicConnection,
    VisonicConnectionCallbacks,
    VisonicConnectionOptions,
    VisonicPanelMetadata,
)
from .connection_test import CLOUD_AUTH_ERRORS
from .const import CONF_PANEL_SERIAL, LOGGER, PIN_REGEX, TEXT_PANEL_MODEL
from .exceptions import VisonicAuthException, VisonicException
from .utils import combine_partition_statuses, get_utc_time, to_bool
from .visonic_data_types import VisonicCoordinatorData
from .visonic_entity_types import PanelState
from .visonic_types import (
    AlarmCommandStatus,
    AlarmPanelCommand,
    AlarmPanelStatus,
    CommandResult,
)

MAP_ALARM_STATUS = {
    "DISARM": AlarmPanelStatus.DISARMED,
    "AWAY": AlarmPanelStatus.ARMED_AWAY,
    "HOME": AlarmPanelStatus.ARMED_HOME,
    "EXIT_AWAY": AlarmPanelStatus.ARMING_AWAY,
    "EXIT_HOME": AlarmPanelStatus.ARMING_HOME,
    "ENTRY_DELAY": AlarmPanelStatus.ENTRY_DELAY,
    "ENTRYDELAY": AlarmPanelStatus.ENTRY_DELAY,
    "PROGRAMMING": AlarmPanelStatus.INSTALLER,
    "ALARM": AlarmPanelStatus.TRIGGERED,
}


@dataclass(slots=True)
class VisonicCloudSettings:
    """Cloud connection settings copied from the config entry."""

    hostname: str
    email: str
    password: str
    code: str
    panel_serial: str
    panel_id: int
    panel_name: str
    update_interval: float
    app_id: str | None = None


class VisonicCloudConnection(VisonicConnection):
    """Class to manage fetching Visonic data from the cloud API."""

    def __init__(
        self,
        settings: VisonicCloudSettings,
        options: VisonicConnectionOptions,
        callbacks: VisonicConnectionCallbacks,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize cloud I/O without Home Assistant runtime objects."""
        super().__init__(options, callbacks)
        self.settings = settings
        self.session = session
        self.login_success = False
        self.cloud_alarm: AlarmSystem | None = None
        self.panel_serial = settings.panel_serial
        self.last_connected_timestamp: datetime = get_utc_time()
        self.never_connected = True
        self.disconnection_counter = 0
        self._last_snapshot = VisonicCoordinatorData()
        self._session_lock = asyncio.Lock()

    def save_connection_entry(self) -> None:
        """Save a changed application ID after successful panel login."""
        if self.cloud_alarm and self.cloud_alarm.api:
            app_id = self.cloud_alarm.api.app_id
            if self.settings.app_id != app_id:
                self.settings.app_id = app_id
                self.callbacks.app_id_changed(app_id)

    async def authenticate(self) -> API | None:
        """Authenticate with the panel."""
        uuid_key = self.settings.app_id
        if not uuid_key:
            # If an app ID has not been created then create one
            uuid_key = str(uuid.uuid4())
        api = API(
            session=self.session,
            hostname=self.settings.hostname,
            app_id=uuid_key,
        )
        # Ensure the REST version is set so the URLs are valid
        await api.set_rest_version()
        if await api.authenticate_user(
            self.settings.email,
            self.settings.password,
        ):
            return api  # return the api
        return None

    @override
    async def async_panel_stop(self) -> None:
        """Disconnect from the cloud visonic server."""
        async with self._session_lock:
            await self._async_panel_stop()

    async def _async_panel_stop(self) -> None:
        """Disconnect while the session lock is held."""
        if self.login_success and self.cloud_alarm:
            try:
                # Try to logout to free up the session
                async with asyncio.timeout(10):
                    await self.cloud_alarm.panel_logout()
            except (
                Error,
                UnauthorizedError,
                OSError,
                TimeoutError,
                aiohttp.ClientError,
            ) as err:
                # Cleanup failures must not invalidate success
                LOGGER.debug(
                    "Cloud panel logout failed (%s): %s", type(err).__name__, err
                )
        self.login_success = False
        self.cloud_alarm = None

    async def _extract_model_and_type(self) -> str:
        """Select a cloud panel and report its model and serial."""
        if self.cloud_alarm is None:
            return ""
        panel_serial = self.settings.panel_serial
        panels: list[dict[str, Any]] = await self.cloud_alarm.api.get_panels()
        if not panel_serial and len(panels) == 1:
            panel_serial = str(panels[0][CONF_PANEL_SERIAL])
        if not panel_serial:
            raise VisonicException("Select a registered cloud panel in reconfiguration")
        if len(panel_serial) == 6:
            # 6 alphanumeric characters
            for panel in panels:
                if str(panel["panel_serial"]).upper() == panel_serial.upper():
                    self.settings.panel_serial = panel_serial
                    self.callbacks.panel_metadata_changed(
                        VisonicPanelMetadata(panel.get(TEXT_PANEL_MODEL), panel_serial)
                    )
                    return panel_serial
        raise VisonicException("Panel serial is not registered to this cloud account")

    async def wait_for_process_status(
        self, process_token: str | None, attempts: int = 5
    ) -> AlarmCommandStatus:
        """Check the process status for up to 5 seconds."""
        # Some commands to the cloud have a process_token to obtain status of
        #   the command after it is sent, did it success or not?
        if self.cloud_alarm is not None:
            if process_token is not None:
                while attempts > 0:
                    attempts -= 1
                    await asyncio.sleep(1.0)
                    processes = await self.cloud_alarm.get_process_status(process_token)
                    for process in processes:
                        if process.status == "succeeded":
                            return AlarmCommandStatus.SUCCESS
                        if process.status == "handled":
                            return AlarmCommandStatus.SUCCESS
                        if process.status == "failed":
                            return AlarmCommandStatus.FAIL_INVALID_STATE
                        if process.status == "error":
                            return AlarmCommandStatus.FAIL_INVALID_STATE
                return AlarmCommandStatus.FAIL_INVALID_RETURN
            return AlarmCommandStatus.FAIL_INVALID_PROCESS_TOKEN
        return AlarmCommandStatus.FAIL_PANEL_NO_CONNECTION

    @override
    def get_panel_pin_code(self, code: str | None) -> tuple[bool, str | None]:
        """Get code code."""
        if self.cloud_alarm is not None and (
            not code
            or (PIN_REGEX.fullmatch(code) and code == self.cloud_alarm.get_user_code())
        ):
            return True, self.cloud_alarm.get_user_code()
        return False, None

    @override
    async def send_command(
        self,
        command: AlarmPanelCommand,
        code: str | None,
    ) -> CommandResult:
        """Send panel command to the cloud."""
        async with self._session_lock:
            return await self._async_send_command(command, code)

    async def _async_send_command(
        self, command: AlarmPanelCommand, code: str | None
    ) -> CommandResult:
        """Renew an expired session once without replaying an accepted command."""
        is_valid, _ = self.get_panel_pin_code(code=code)
        if not is_valid:
            return CommandResult(
                AlarmCommandStatus.FAIL_INVALID_CODE,
            )

        acs = AlarmCommandStatus.FAIL_INVALID_RETURN
        if self.cloud_alarm is not None:
            submitted = False
            renewed = False
            process_token = None
            user_settings_allowed = True
            LOGGER.debug("Sending panel command %s", str(command.name))
            try:
                while True:
                    try:
                        if not submitted:
                            (
                                user_settings_allowed,
                                process_token,
                            ) = await self._async_submit_command(command)
                            submitted = True
                        if not user_settings_allowed:
                            acs = AlarmCommandStatus.FAIL_USER_CONFIG_PREVENTED
                        elif process_token is not None:
                            acs = await self.wait_for_process_status(process_token)
                        break
                    except UnauthorizedError, SessionTokenError, UserAuthRequiredError:
                        if renewed:
                            raise
                        renewed = True
                        await self._async_panel_reconnect()
            except (UnauthorizedError, SessionTokenError, UserAuthRequiredError) as err:
                raise HomeAssistantError(
                    f"Unable to communicate with Visonic panel {self.settings.panel_id}"
                ) from err
            except CLOUD_AUTH_ERRORS as ex:
                raise VisonicAuthException(
                    "Cloud Authentication Error - panel connection failure"
                ) from ex
            except VisonicAuthException:
                raise
            except (Error, VisonicException) as err:
                raise HomeAssistantError(
                    f"Unable to communicate with Visonic panel {self.settings.panel_id}"
                ) from err

        # schedule an update in 5 seconds time (if nothing else changes in between)
        self.callbacks.state_changed(5.0)
        return CommandResult(acs)

    async def _async_submit_command(
        self, command: AlarmPanelCommand
    ) -> tuple[bool, str | None]:
        """Check remote-control policy and submit once without confirming the result."""
        if self.cloud_alarm is None:
            return True, None
        match command:
            case AlarmPanelCommand.DISARM:
                if not self.options.enable_remote_disarm:
                    return False, None
                return True, await self.cloud_alarm.disarm()
            case AlarmPanelCommand.ARM_AWAY:
                if not self.options.enable_remote_arm:
                    return False, None
                return True, await self.cloud_alarm.arm_away()
            case AlarmPanelCommand.ARM_HOME:
                if (
                    not self.options.enable_remote_arm
                    or not self.options.arm_home_enabled
                ):
                    return False, None
                return True, await self.cloud_alarm.arm_home()
            case AlarmPanelCommand.ARM_AWAY_INSTANT:
                if not self.options.enable_remote_arm:
                    return False, None
                return True, await self.cloud_alarm.arm_away_instant()
            case AlarmPanelCommand.ARM_HOME_INSTANT:
                if (
                    not self.options.enable_remote_arm
                    or not self.options.arm_home_enabled
                ):
                    return False, None
                return True, await self.cloud_alarm.arm_home_instant()

    @override
    async def async_panel_connect(self) -> bool:
        """Connect to the cloud server."""
        async with self._session_lock:
            return await self._async_panel_connect()

    async def _async_panel_connect(self) -> bool:
        """Connect while the session lock is held."""
        # Initialize API
        try:
            self.login_success = False
            # Authenticate with the cloud server
            api = await self.authenticate()
            if api:
                LOGGER.debug("Panel auth success")
                self.cloud_alarm = AlarmSystem(api)
                self.panel_serial = await self._extract_model_and_type()
                # Login to the Panel via the cloud server
                if await self.cloud_alarm.panel_login(
                    self.panel_serial,
                    self.settings.code,
                ):
                    LOGGER.debug("Panel login success")
                    self.login_success = True
                    # The login details are new so save them
                    self.save_connection_entry()
                    return True
        except CLOUD_AUTH_ERRORS as ex:
            raise VisonicAuthException(
                "Cloud Authentication Error - panel connection failure"
            ) from ex
        except VisonicAuthException:
            raise
        except Exception as ex:
            raise VisonicException(
                "Cloud Connection Error - panel connection failure"
            ) from ex

        raise VisonicAuthException("Cloud credentials or panel user code were rejected")

    async def async_panel_reconnect(self) -> None:
        """Service call to re-connect the comms connection."""
        async with self._session_lock:
            await self._async_panel_reconnect()

    async def _async_panel_reconnect(self) -> None:
        """Replace a cloud session without releasing the session lock."""
        # Stop all current access to the panel
        await self._async_panel_stop()
        self.disconnection_counter += 1
        # Connect to the cloud server and panel
        await self._async_panel_connect()

    def _determine_armcode(self, p: Partition) -> AlarmPanelStatus:
        """Get the armed/disarmed state of this partition."""
        if p.status is None or p.state is None:
            return AlarmPanelStatus.UNKNOWN
        key = p.status + "_" + p.state if p.status else p.state
        return MAP_ALARM_STATUS.get(key, AlarmPanelStatus.UNKNOWN)

    @override
    async def create_state_snapshot(self) -> VisonicCoordinatorData:
        """Fetch data from Visonic API with auto-reauth."""
        async with self._session_lock:
            return await self._async_create_state_snapshot()

    async def _async_create_state_snapshot(self) -> VisonicCoordinatorData:
        """Renew an expired session once and read its replacement while locked."""
        try:
            try:
                return await self._async_read_state_snapshot()
            except UnauthorizedError, SessionTokenError, UserAuthRequiredError:
                LOGGER.debug("Visonic session expired, re-authenticating")
                await self._async_panel_reconnect()
                return await self._async_read_state_snapshot()
        except VisonicAuthException:
            raise
        except CLOUD_AUTH_ERRORS as err:
            raise VisonicAuthException("Cloud authentication failed") from err
        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with Visonic Cloud: {err}"
            ) from err

    async def _async_read_state_snapshot(self) -> VisonicCoordinatorData:
        """Read one complete snapshot while the session lock is held."""
        if not self.login_success or self.cloud_alarm is None:
            # We are not connected to the cloud server, so try to reconnect
            LOGGER.debug("Updating data - Cloud connection has not been made")
            await self._async_panel_reconnect()

        if not self.login_success or self.cloud_alarm is None:
            # We are still not connected to the cloud server (having tried reconnect)
            self._last_snapshot = VisonicCoordinatorData(
                connected=False,
                ispowermaster=True,
                mode="cloud",
                achieved_powerlink=True,
                model=self.settings.panel_name,
            )
            return self._last_snapshot

        # We're connected to the visonic cloud server and we are logged in

        timenow: datetime = get_utc_time()
        panel_data = await self.cloud_alarm.get_panel_state()

        if not panel_data.connected:
            # The panel is not responsive so try to reconnect
            #  This may be a temporary thing though so have timeouts
            timeout: float = min(60, 2.5 * self.settings.update_interval)
            delta_time: timedelta = timenow - self.last_connected_timestamp
            if self.never_connected or delta_time >= timedelta(seconds=timeout):
                # not less than 60 seconds, but allow 2 tries at updating before it's considered a timeout
                timeout = min(90, 4.5 * self.settings.update_interval)
                if delta_time > timedelta(seconds=timeout):
                    # not less than 90 seconds, but allow 4 tries at updating before it's considered a reconnect
                    LOGGER.debug("Updating data - re-connection to cloud server")
                    self.last_connected_timestamp = timenow
                    await self._async_panel_reconnect()
                LOGGER.debug(
                    "Updating data - panel is not connected to the cloud, no access!"
                )
                self._last_snapshot = VisonicCoordinatorData(
                    connected=False,
                    ispowermaster=True,
                    mode="cloud",
                    achieved_powerlink=True,
                    model=self.settings.panel_name,  # .panel_model,
                )
                return self._last_snapshot
            LOGGER.debug("Cloud panel disconnected; waiting before reconnecting")
            return replace(self._last_snapshot, connected=False)

        # The visonic cloud server is currently connected to the panel and the panel is responding
        self.last_connected_timestamp = timenow
        self.never_connected = False
        panelstate = self.process_devices(panel_data.devices)
        armcode = combine_partition_statuses(
            self._determine_armcode(part) for part in panel_data.partitions
        )
        panelstate.attributes["ready"] = bool(panel_data.partitions) and all(
            part.ready for part in panel_data.partitions
        )

        new_data = VisonicCoordinatorData(
            connected=True,
            ispowermaster=True,
            mode="cloud",
            achieved_powerlink=True,
            model=self.settings.panel_name,  # .panel_model,
            disconnection_count=self.disconnection_counter,
            panelstate=panelstate,
            armcode=armcode,
            siren_active=panel_data.alarm_active,
        )
        self._last_snapshot = new_data
        return new_data

    def process_devices(self, devices: Sequence[Device]) -> PanelState:
        """Process the devices from the panel."""
        panelstate = PanelState(
            emulationmode="cloud",
            trouble="none",
            battery_level=100,
            tamper=False,
        )
        for device in devices:
            if isinstance(device, PanelDevice):
                panelstate.battery_level = 0 if device.low_battery else 100
                panelstate.tamper = to_bool(device.tamper)
                panelstate.trouble = device.trouble
        return panelstate
