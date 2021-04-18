"""Support for Overkiz cover - shutters etc."""
import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_AWNING,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_CURTAIN,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_GATE,
    DEVICE_CLASS_SHUTTER,
    DEVICE_CLASS_WINDOW,
    DOMAIN as COVER,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)

from .const import DOMAIN
from .overkiz_entity import OverkizEntity

_LOGGER = logging.getLogger(__name__)

ATTR_OBSTRUCTION_DETECTED = "obstruction-detected"

COMMAND_CYCLE = "cycle"
COMMAND_CLOSE = "close"
COMMAND_CLOSE_SLATS = "closeSlats"
COMMAND_DOWN = "down"
COMMAND_MY = "my"
COMMAND_OPEN = "open"
COMMAND_OPEN_SLATS = "openSlats"
COMMAND_SET_CLOSURE = "setClosure"
COMMAND_SET_ORIENTATION = "setOrientation"
COMMAND_SET_PEDESTRIAN_POSITION = "setPedestrianPosition"
COMMAND_SET_POSITION = "setPosition"
COMMAND_STOP = "stop"
COMMAND_STOP_IDENTIFY = "stopIdentify"
COMMAND_UP = "up"

COMMANDS_STOP = [COMMAND_STOP, COMMAND_STOP_IDENTIFY, COMMAND_MY]
COMMANDS_STOP_TILT = [COMMAND_STOP, COMMAND_STOP_IDENTIFY, COMMAND_MY]
COMMANDS_OPEN = [COMMAND_OPEN, COMMAND_UP, COMMAND_CYCLE]
COMMANDS_OPEN_TILT = [COMMAND_OPEN_SLATS]
COMMANDS_CLOSE = [COMMAND_CLOSE, COMMAND_DOWN, COMMAND_CYCLE]
COMMANDS_CLOSE_TILT = [COMMAND_CLOSE_SLATS]
COMMANDS_SET_POSITION = [
    COMMAND_SET_POSITION,
    COMMAND_SET_CLOSURE,
    COMMAND_SET_PEDESTRIAN_POSITION,
]
COMMANDS_SET_TILT_POSITION = [COMMAND_SET_ORIENTATION]

CORE_CLOSURE_STATE = "core:ClosureState"
CORE_CLOSURE_OR_ROCKER_POSITION_STATE = "core:ClosureOrRockerPositionState"
CORE_DEPLOYMENT_STATE = "core:DeploymentState"
CORE_MEMORIZED_1_POSITION_STATE = "core:Memorized1PositionState"
CORE_OPEN_CLOSED_PARTIAL_STATE = "core:OpenClosedPartialState"
CORE_OPEN_CLOSED_PEDESTRIAN_STATE = "core:OpenClosedPedestrianState"
CORE_OPEN_CLOSED_STATE = "core:OpenClosedState"
CORE_OPEN_CLOSED_UNKNOWN_STATE = "core:OpenClosedUnknownState"
CORE_PEDESTRIAN_POSITION_STATE = "core:PedestrianPositionState"
CORE_PRIORITY_LOCK_TIMER_STATE = "core:PriorityLockTimerState"
CORE_SLATS_OPEN_CLOSED_STATE = "core:SlatsOpenClosedState"
CORE_SLATE_ORIENTATION_STATE = "core:SlateOrientationState"
CORE_SLATS_ORIENTATION_STATE = "core:SlatsOrientationState"
CORE_TARGET_CLOSURE_STATE = "core:TargetClosureState"

MYFOX_SHUTTER_STATUS_STATE = "myfox:ShutterStatusState"

IO_PRIORITY_LOCK_LEVEL_STATE = "io:PriorityLockLevelState"

STATE_CLOSED = "closed"

OVERKIZ_COVER_DEVICE_CLASSES = {
    "Awning": DEVICE_CLASS_AWNING,
    "Blind": DEVICE_CLASS_BLIND,
    "Curtain": DEVICE_CLASS_CURTAIN,
    "ExteriorScreen": DEVICE_CLASS_BLIND,
    "ExteriorVenetianBlind": DEVICE_CLASS_BLIND,
    "GarageDoor": DEVICE_CLASS_GARAGE,
    "Gate": DEVICE_CLASS_GATE,
    "MyFoxSecurityCamera": DEVICE_CLASS_SHUTTER,
    "Pergola": DEVICE_CLASS_AWNING,
    "RollerShutter": DEVICE_CLASS_SHUTTER,
    "SwingingShutter": DEVICE_CLASS_SHUTTER,
    "VeluxInteriorBlind": DEVICE_CLASS_BLIND,
    "Window": DEVICE_CLASS_WINDOW,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Overkiz covers from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        OverkizCover(device.deviceurl, coordinator)
        for device in data["platforms"][COVER]
    ]

    async_add_entities(entities)


class OverkizCover(OverkizEntity, CoverEntity):
    """Representation of a Overkiz Cover."""

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = self.executor.select_state(
            CORE_CLOSURE_STATE,
            CORE_DEPLOYMENT_STATE,
            CORE_PEDESTRIAN_POSITION_STATE,
            CORE_TARGET_CLOSURE_STATE,
            CORE_CLOSURE_OR_ROCKER_POSITION_STATE,
        )

        # Uno devices can have a position not in 0 to 100 range when unknown
        if position is None or position < 0 or position > 100:
            return None

        if not self._reversed_position_device():
            position = 100 - position

        return position

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = self.executor.select_state(
            CORE_SLATS_ORIENTATION_STATE, CORE_SLATE_ORIENTATION_STATE
        )
        return 100 - position if position is not None else None

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = 100 - kwargs.get[ATTR_POSITION]

        if self._reversed_position_device():
            position = kwargs.get[ATTR_POSITION]

        await self.executor.async_execute_command(
            self.executor.select_command(*COMMANDS_SET_POSITION), position
        )

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        await self.executor.async_execute_command(
            self.executor.select_command(*COMMANDS_SET_TILT_POSITION),
            100 - kwargs[ATTR_TILT_POSITION],
        )

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        state = self.executor.select_state(
            CORE_OPEN_CLOSED_STATE,
            CORE_SLATS_OPEN_CLOSED_STATE,
            CORE_OPEN_CLOSED_PARTIAL_STATE,
            CORE_OPEN_CLOSED_PEDESTRIAN_STATE,
            CORE_OPEN_CLOSED_UNKNOWN_STATE,
            MYFOX_SHUTTER_STATUS_STATE,
        )

        if state is not None:
            return state == STATE_CLOSED

        if self.current_cover_position is not None:
            return self.current_cover_position == 0

        if self.current_cover_tilt_position is not None:
            return self.current_cover_tilt_position == 0

        return None

    @property
    def device_class(self):
        """Return the class of the device."""
        return (
            OVERKIZ_COVER_DEVICE_CLASSES.get(self.device.widget)
            or OVERKIZ_COVER_DEVICE_CLASSES.get(self.device.ui_class)
            or DEVICE_CLASS_BLIND
        )

    async def async_open_cover(self, **_):
        """Open the cover."""
        await self.executor.async_execute_command(
            self.executor.select_command(*COMMANDS_OPEN)
        )

    async def async_open_cover_tilt(self, **_):
        """Open the cover tilt."""
        await self.executor.async_execute_command(
            self.executor.select_command(*COMMANDS_OPEN_TILT)
        )

    async def async_close_cover(self, **_):
        """Close the cover."""
        await self.executor.async_execute_command(
            self.executor.select_command(*COMMANDS_CLOSE)
        )

    async def async_close_cover_tilt(self, **_):
        """Close the cover tilt."""
        await self.executor.async_execute_command(
            self.executor.select_command(*COMMANDS_CLOSE_TILT)
        )

    async def async_stop_cover(self, **_):
        """Stop the cover."""
        await self.async_cancel_or_stop_cover(
            COMMANDS_OPEN + COMMANDS_SET_POSITION + COMMANDS_CLOSE,
            COMMANDS_STOP,
        )

    async def async_stop_cover_tilt(self, **_):
        """Stop the cover tilt."""
        await self.async_cancel_or_stop_cover(
            COMMANDS_OPEN_TILT + COMMANDS_SET_TILT_POSITION + COMMANDS_CLOSE_TILT,
            COMMANDS_STOP_TILT,
        )

    async def async_cancel_or_stop_cover(self, cancel_commands, stop_commands) -> None:
        """Cancel running execution or send stop command."""
        # Cancelling a running execution will stop the cover movement
        # Retrieve executions initiated via Home Assistant from Data Update Coordinator queue
        exec_id = next(
            (
                exec_id
                # Reverse dictionary to cancel the last added execution
                for exec_id, execution in reversed(self.coordinator.executions.items())
                if execution.get("deviceurl") == self.device.deviceurl
                and execution.get("command_name") in cancel_commands
            ),
            None,
        )

        if exec_id:
            return await self.executor.async_cancel_command(exec_id)

        # Retrieve executions initiated outside Home Assistant via API
        executions = await self.coordinator.client.get_current_executions()
        exec_id = next(
            (
                execution.id
                for execution in executions
                # Reverse dictionary to cancel the last added execution
                for action in reversed(execution.action_group.get("actions"))
                for command in action.get("commands")
                if action.get("deviceurl") == self.device.deviceurl
                and command.get("name") in cancel_commands
            ),
            None,
        )

        if exec_id:
            return await self.executor.async_cancel_command(exec_id)

        # Fallback to available stop commands when no executions are found
        # Stop commands don't work with all devices, due to a bug in Somfy service
        await self.executor.async_execute_command(
            self.executor.select_command(*stop_commands)
        )

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return any(
            execution.get("deviceurl") == self.device.deviceurl
            and execution.get("command_name") in COMMANDS_OPEN + COMMANDS_OPEN_TILT
            for execution in self.coordinator.executions.values()
        )

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return any(
            execution.get("deviceurl") == self.device.deviceurl
            and execution.get("command_name") in COMMANDS_CLOSE + COMMANDS_CLOSE_TILT
            for execution in self.coordinator.executions.values()
        )

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = super().device_state_attributes or {}

        # Obstruction Detected attribute is used by HomeKit
        if self.executor.has_state(IO_PRIORITY_LOCK_LEVEL_STATE):
            attr[ATTR_OBSTRUCTION_DETECTED] = True

        return attr

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0

        if self.executor.has_command(*COMMANDS_OPEN_TILT):
            supported_features |= SUPPORT_OPEN_TILT

            if self.executor.has_command(*COMMANDS_STOP_TILT):
                supported_features |= SUPPORT_STOP_TILT

        if self.executor.has_command(*COMMANDS_CLOSE_TILT):
            supported_features |= SUPPORT_CLOSE_TILT

        if self.executor.has_command(*COMMANDS_SET_TILT_POSITION):
            supported_features |= SUPPORT_SET_TILT_POSITION

        if self.executor.has_command(*COMMANDS_SET_POSITION):
            supported_features |= SUPPORT_SET_POSITION

        if self.executor.has_command(*COMMANDS_OPEN):
            supported_features |= SUPPORT_OPEN

            if self.executor.has_command(*COMMANDS_STOP):
                supported_features |= SUPPORT_STOP

        if self.executor.has_command(*COMMANDS_CLOSE):
            supported_features |= SUPPORT_CLOSE

        return supported_features

    def _reversed_position_device(self):
        """Return true if the device need a reversed position that can not be obtained via the API."""
        return "Horizontal" in self.device.widget
