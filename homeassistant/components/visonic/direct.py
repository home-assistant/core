"""Direct panel connection and state conversion."""

import asyncio
from typing import Any, override

from pyvisonic import (
    AlCondition,
    AlPanelCommand,
    AlTerminationType,
    VisonicClient,
    VisonicClientCallbacks,
    VisonicClientSettings,
)

from .connection import (
    VisonicConnection,
    VisonicConnectionCallbacks,
    VisonicConnectionOptions,
    VisonicPanelMetadata,
)
from .const import CLIENT_VERSION, LOGGER, PIN_REGEX, TEXT_CLIENT_VERSION
from .utils import combine_partition_statuses
from .visonic_data_types import VisonicCoordinatorData
from .visonic_entity_types import PanelState
from .visonic_types import (
    AlarmCommandStatus,
    AlarmPanelCommand,
    AlarmPanelStatus,
    CommandResult,
)

ARM_COMMANDS = {
    AlarmPanelCommand.ARM_HOME,
    AlarmPanelCommand.ARM_AWAY,
    AlarmPanelCommand.ARM_HOME_INSTANT,
    AlarmPanelCommand.ARM_AWAY_INSTANT,
}
ARM_DISARM_COMMANDS = ARM_COMMANDS | {AlarmPanelCommand.DISARM}


class VisonicDirectConnection(VisonicConnection):
    """Manage the standalone client for a direct panel connection."""

    def __init__(
        self,
        settings: VisonicClientSettings,
        options: VisonicConnectionOptions,
        callbacks: VisonicConnectionCallbacks,
    ) -> None:
        """Initialize the client using settings and explicit callbacks."""
        super().__init__(options, callbacks)
        self._state_received = asyncio.Event()
        self._client = VisonicClient(
            settings,
            VisonicClientCallbacks(
                state_change=self._handle_state_change,
                panel_change=self._handle_panel_change,
                baud_change=self.callbacks.baud_changed,
                problem=self._handle_panel_problem,
            ),
        )

    def _handle_state_change(self) -> None:
        """Wake startup and notify the coordinator when panel state changes."""
        self._state_received.set()
        self.callbacks.state_changed(0.2)

    @override
    def update_options(self, options: VisonicConnectionOptions) -> None:
        """Apply options to the standalone client."""
        super().update_options(options)
        self._client.settings.retry_count = options.retry_count
        self._client.settings.retry_delay = options.retry_delay

    def _handle_panel_change(
        self, condition: AlCondition, data: dict[str, Any] | None
    ) -> None:
        """Translate client notifications into connection events."""
        if condition == AlCondition.DOWNLOAD_SUCCESS:
            self.callbacks.panel_metadata_changed(
                VisonicPanelMetadata(
                    self._client.panel_model, self._client.panel_ident or None
                )
            )
        elif condition == AlCondition.STARTUP_SUCCESS:
            self.callbacks.panel_ready()

    def _handle_panel_problem(self, termination: AlTerminationType) -> None:
        """Report a terminal flood recovery failure to the integration owner."""
        if (
            termination == AlTerminationType.FLOOD_RECOVERY_FAILED
            and self.callbacks.recovery_failed is not None
        ):
            self.callbacks.recovery_failed()

    def _get_panel_state(self) -> PanelState:
        attributes = self._client.get_panel_status_dict(self.options.eprom_attributes)
        attributes[TEXT_CLIENT_VERSION] = CLIENT_VERSION
        return PanelState(
            attributes.get("emulationmode", ""),
            attributes.get("trouble", ""),
            attributes.get("battery_level", 0),
            attributes.get("tamper", False),
            attributes,
        )

    @override
    async def async_panel_connect(self) -> bool:
        """Start the standalone panel connection."""
        self._client.settings.offload_f4_ack = False
        self._state_received.clear()
        if not self._client.connect():
            return False
        # Older PowerMax panels can need up to 90 seconds for Powerlink initialization.
        async with asyncio.timeout(180):
            while not self._client.is_panel_connected():
                await self._state_received.wait()
                self._state_received.clear()
        return True

    @override
    async def async_panel_stop(self) -> None:
        """Stop the standalone panel client."""
        await self._client.async_panel_stop()

    @override
    async def send_command(
        self,
        command: AlarmPanelCommand,
        code: str | None,
    ) -> CommandResult:
        """Common send command function."""
        if not code and self.options.arm_without_usercode and command in ARM_COMMANDS:
            code = None
        else:
            is_valid, code = self.get_panel_pin_code(code=code)
            if not is_valid:
                return CommandResult(AlarmCommandStatus.FAIL_INVALID_CODE)

        if command in ARM_DISARM_COMMANDS:
            if not (
                (
                    command == AlarmPanelCommand.DISARM
                    and self.options.enable_remote_disarm
                )
                or (
                    command != AlarmPanelCommand.DISARM
                    and self.options.enable_remote_arm
                )
            ):
                return CommandResult(
                    AlarmCommandStatus.FAIL_USER_CONFIG_PREVENTED,
                )

            cmd = AlPanelCommand(command)
            status = await self._client.send_command(cmd, code, None)
            return CommandResult(AlarmCommandStatus(status))
        return CommandResult(AlarmCommandStatus.FAIL_PANEL_CONFIG_PREVENTED)

    @override
    def get_panel_pin_code(self, code: str | None) -> tuple[bool, str | None]:
        """Get code."""
        if code:
            if isinstance(code, str) and PIN_REGEX.fullmatch(code):
                return True, code
            return False, None
        if self._client.achieved_powerlink():
            return True, None
        LOGGER.warning(
            "Warning: [get_panel_pin_code] Valid 4 digit PIN not found, panelmode is %s",
            self._client.panel_mode_str,
        )
        return False, None

    @override
    async def create_state_snapshot(self) -> VisonicCoordinatorData:
        """Return the combined state of the whole panel."""
        if not self._client.is_panel_connected():
            return VisonicCoordinatorData(connected=False)
        partitions = self._client.get_partitions_in_use() or {0}
        armcode = combine_partition_statuses(
            AlarmPanelStatus(self._client.get_partition_status(partition).value)
            for partition in partitions
        )
        return VisonicCoordinatorData(
            connected=True,
            ispowermaster=self._client.is_power_master(),
            mode=self._client.panel_mode_str.lower(),
            achieved_powerlink=self._client.achieved_powerlink(),
            disconnection_count=self._client.disconnection_count,
            model=self._client.panel_model,
            statusdict=self._client.get_panel_status_dict(),
            panelstate=self._get_panel_state(),
            armcode=armcode,
            siren_active=self._client.is_any_siren_active()[0],
        )
