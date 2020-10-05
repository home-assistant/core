"""Support for TaHoma cover - shutters etc."""
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
from .tahoma_device import TahomaDevice

_LOGGER = logging.getLogger(__name__)

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
COMMAND_SET_POSITION_AND_LINEAR_SPEED = "setPositionAndLinearSpeed"
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
CORE_SLATS_ORIENTATION_STATE = "core:SlatsOrientationState"
CORE_TARGET_CLOSURE_STATE = "core:TargetClosureState"
MYFOX_SHUTTER_STATUS_STATE = "myfox:ShutterStatusState"

ICON_LOCK_ALERT = "mdi:lock-alert"
ICON_WEATHER_WINDY = "mdi:weather-windy"

IO_PRIORITY_LOCK_ORIGINATOR_STATE = "io:PriorityLockOriginatorState"

STATE_CLOSED = "closed"

SERVICE_COVER_MY_POSITION = "set_cover_my_position"
SERVICE_COVER_POSITION_LOW_SPEED = "set_cover_position_low_speed"

SUPPORT_MY = 512
SUPPORT_COVER_POSITION_LOW_SPEED = 1024


TAHOMA_COVER_DEVICE_CLASSES = {
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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the TaHoma covers from a config entry."""
    data = hass.data[DOMAIN]
    coordinator = data["coordinator"]

    entities = [
        TahomaCover(device.deviceurl, coordinator)
        for device in data["entities"].get(COVER)
    ]

    async_add_entities(entities)


class TahomaCover(TahomaDevice, CoverEntity):
    """Representation of a TaHoma Cover."""

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = self.select_state(
            CORE_CLOSURE_STATE,
            CORE_DEPLOYMENT_STATE,
            CORE_PEDESTRIAN_POSITION_STATE,
            CORE_TARGET_CLOSURE_STATE,
            CORE_CLOSURE_OR_ROCKER_POSITION_STATE,
        )

        # Uno devices can have a position not in 0 to 100 range when unknown
        if position is None or position < 0 or position > 100:
            return None

        if "Horizontal" not in self.device.widget:
            position = 100 - position

        return position

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = self.select_state(CORE_SLATS_ORIENTATION_STATE)
        return 100 - position if position is not None else None

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = 100 - kwargs.get(ATTR_POSITION, 0)

        # HorizontalAwning devices need a reversed position that can not be obtained via the API
        if "Horizontal" in self.device.widget:
            position = kwargs.get(ATTR_POSITION, 0)

        await self.async_execute_command(
            self.select_command(*COMMANDS_SET_POSITION), position
        )

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        await self.async_execute_command(
            self.select_command(*COMMANDS_SET_TILT_POSITION),
            100 - kwargs.get(ATTR_TILT_POSITION, 0),
        )

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        state = self.select_state(
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
            TAHOMA_COVER_DEVICE_CLASSES.get(self.device.widget)
            or TAHOMA_COVER_DEVICE_CLASSES.get(self.device.ui_class)
            or DEVICE_CLASS_BLIND
        )

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if (
            self.has_state(CORE_PRIORITY_LOCK_TIMER_STATE)
            and self.select_state(CORE_PRIORITY_LOCK_TIMER_STATE) > 0
        ):
            if self.select_state(IO_PRIORITY_LOCK_ORIGINATOR_STATE) == "wind":
                return ICON_WEATHER_WINDY
            return ICON_LOCK_ALERT

        return None

    async def async_open_cover(self, **_):
        """Open the cover."""
        await self.async_execute_command(self.select_command(*COMMANDS_OPEN))

    async def async_open_cover_tilt(self, **_):
        """Open the cover tilt."""
        await self.async_execute_command(self.select_command(*COMMANDS_OPEN_TILT))

    async def async_close_cover(self, **_):
        """Close the cover."""
        await self.async_execute_command(self.select_command(*COMMANDS_CLOSE))

    async def async_close_cover_tilt(self, **_):
        """Close the cover tilt."""
        await self.async_execute_command(self.select_command(*COMMANDS_CLOSE_TILT))

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
            return await self.async_cancel_command(exec_id)

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
            return await self.async_cancel_command(exec_id)

        # Fallback to available stop commands when no executions are found
        # Stop commands don't work with all devices, due to a bug in Somfy service
        await self.async_execute_command(self.select_command(*stop_commands))

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
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0

        if self.has_command(*COMMANDS_OPEN_TILT):
            supported_features |= SUPPORT_OPEN_TILT

            if self.has_command(*COMMANDS_STOP_TILT):
                supported_features |= SUPPORT_STOP_TILT

        if self.has_command(*COMMANDS_CLOSE_TILT):
            supported_features |= SUPPORT_CLOSE_TILT

        if self.has_command(*COMMANDS_SET_TILT_POSITION):
            supported_features |= SUPPORT_SET_TILT_POSITION

        if self.has_command(*COMMANDS_SET_POSITION):
            supported_features |= SUPPORT_SET_POSITION

        if self.has_command(*COMMANDS_OPEN):
            supported_features |= SUPPORT_OPEN

            if self.has_command(*COMMANDS_STOP):
                supported_features |= SUPPORT_STOP

        if self.has_command(*COMMANDS_CLOSE):
            supported_features |= SUPPORT_CLOSE

        if self.has_command(COMMAND_SET_POSITION_AND_LINEAR_SPEED):
            supported_features |= SUPPORT_COVER_POSITION_LOW_SPEED

        if self.has_command(COMMAND_MY):
            supported_features |= SUPPORT_MY

        return supported_features
