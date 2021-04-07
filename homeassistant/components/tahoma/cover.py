"""Support for Tahoma cover - shutters etc."""
from datetime import timedelta
import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_AWNING,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_CURTAIN,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_SHUTTER,
    DEVICE_CLASS_WINDOW,
    CoverEntity,
)
from homeassistant.util.dt import utcnow

from . import DOMAIN as TAHOMA_DOMAIN, TahomaDevice

_LOGGER = logging.getLogger(__name__)

ATTR_MEM_POS = "memorized_position"
ATTR_RSSI_LEVEL = "rssi_level"
ATTR_LOCK_START_TS = "lock_start_ts"
ATTR_LOCK_END_TS = "lock_end_ts"
ATTR_LOCK_LEVEL = "lock_level"
ATTR_LOCK_ORIG = "lock_originator"

HORIZONTAL_AWNING = "io:HorizontalAwningIOComponent"

TAHOMA_DEVICE_CLASSES = {
    HORIZONTAL_AWNING: DEVICE_CLASS_AWNING,
    "io:AwningValanceIOComponent": DEVICE_CLASS_AWNING,
    "io:DiscreteGarageOpenerWithPartialPositionIOComponent": DEVICE_CLASS_GARAGE,
    "io:DiscreteGarageOpenerIOComponent": DEVICE_CLASS_GARAGE,
    "io:ExteriorVenetianBlindIOComponent": DEVICE_CLASS_BLIND,
    "io:GarageOpenerIOComponent": DEVICE_CLASS_GARAGE,
    "io:RollerShutterGenericIOComponent": DEVICE_CLASS_SHUTTER,
    "io:RollerShutterUnoIOComponent": DEVICE_CLASS_SHUTTER,
    "io:RollerShutterVeluxIOComponent": DEVICE_CLASS_SHUTTER,
    "io:RollerShutterWithLowSpeedManagementIOComponent": DEVICE_CLASS_SHUTTER,
    "io:VerticalExteriorAwningIOComponent": DEVICE_CLASS_AWNING,
    "io:VerticalInteriorBlindVeluxIOComponent": DEVICE_CLASS_BLIND,
    "io:WindowOpenerVeluxIOComponent": DEVICE_CLASS_WINDOW,
    "rts:BlindRTSComponent": DEVICE_CLASS_BLIND,
    "rts:CurtainRTSComponent": DEVICE_CLASS_CURTAIN,
    "rts:DualCurtainRTSComponent": DEVICE_CLASS_CURTAIN,
    "rts:ExteriorVenetianBlindRTSComponent": DEVICE_CLASS_BLIND,
    "rts:RollerShutterRTSComponent": DEVICE_CLASS_SHUTTER,
    "rts:VenetianBlindRTSComponent": DEVICE_CLASS_BLIND,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tahoma covers."""
    if discovery_info is None:
        return
    controller = hass.data[TAHOMA_DOMAIN]["controller"]
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]["devices"]["cover"]:
        devices.append(TahomaCover(device, controller))
    add_entities(devices, True)


class TahomaCover(TahomaDevice, CoverEntity):
    """Representation a Tahoma Cover."""

    def __init__(self, tahoma_device, controller):
        """Initialize the device."""
        super().__init__(tahoma_device, controller)

        self._closure = 0
        # 100 equals open
        self._position = 100
        self._closed = False
        self._rssi_level = None
        self._icon = None
        # Can be 0 and bigger
        self._lock_timer = 0
        self._lock_start_ts = None
        self._lock_end_ts = None
        # Can be 'comfortLevel1', 'comfortLevel2', 'comfortLevel3',
        # 'comfortLevel4', 'environmentProtection', 'humanProtection',
        # 'userLevel1', 'userLevel2'
        self._lock_level = None
        # Can be 'LSC', 'SAAC', 'SFC', 'UPS', 'externalGateway', 'localUser',
        # 'myself', 'rain', 'security', 'temperature', 'timer', 'user', 'wind'
        self._lock_originator = None

    def update(self):
        """Update method."""
        self.controller.get_states([self.tahoma_device])

        # For vertical covers
        self._closure = self.tahoma_device.active_states.get("core:ClosureState")
        # For horizontal covers
        if self._closure is None:
            self._closure = self.tahoma_device.active_states.get("core:DeploymentState")

        # For all, if available
        if "core:PriorityLockTimerState" in self.tahoma_device.active_states:
            old_lock_timer = self._lock_timer
            self._lock_timer = self.tahoma_device.active_states[
                "core:PriorityLockTimerState"
            ]
            # Derive timestamps from _lock_timer, only if not already set or
            # something has changed
            if self._lock_timer > 0:
                _LOGGER.debug("Update %s, lock_timer: %d", self._name, self._lock_timer)
                if self._lock_start_ts is None:
                    self._lock_start_ts = utcnow()
                if self._lock_end_ts is None or old_lock_timer != self._lock_timer:
                    self._lock_end_ts = utcnow() + timedelta(seconds=self._lock_timer)
            else:
                self._lock_start_ts = None
                self._lock_end_ts = None
        else:
            self._lock_timer = 0
            self._lock_start_ts = None
            self._lock_end_ts = None

        self._lock_level = self.tahoma_device.active_states.get(
            "io:PriorityLockLevelState"
        )

        self._lock_originator = self.tahoma_device.active_states.get(
            "io:PriorityLockOriginatorState"
        )

        self._rssi_level = self.tahoma_device.active_states.get("core:RSSILevelState")

        # Define which icon to use
        if self._lock_timer > 0:
            if self._lock_originator == "wind":
                self._icon = "mdi:weather-windy"
            else:
                self._icon = "mdi:lock-alert"
        else:
            self._icon = None

        # Define current position.
        #   _position: 0 is closed, 100 is fully open.
        #   'core:ClosureState': 100 is closed, 0 is fully open.
        if self._closure is not None:
            if self.tahoma_device.type == HORIZONTAL_AWNING:
                self._position = self._closure
            else:
                self._position = 100 - self._closure
            if self._position <= 5:
                self._position = 0
            if self._position >= 95:
                self._position = 100
            self._closed = self._position == 0
        else:
            self._position = None
            if "core:OpenClosedState" in self.tahoma_device.active_states:
                self._closed = (
                    self.tahoma_device.active_states["core:OpenClosedState"] == "closed"
                )
            if "core:OpenClosedPartialState" in self.tahoma_device.active_states:
                self._closed = (
                    self.tahoma_device.active_states["core:OpenClosedPartialState"]
                    == "closed"
                )
            else:
                self._closed = False

        _LOGGER.debug("Update %s, position: %d", self._name, self._position)

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        return self._position

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if self.tahoma_device.type == "io:WindowOpenerVeluxIOComponent":
            command = "setClosure"
        else:
            command = "setPosition"

        if self.tahoma_device.type == HORIZONTAL_AWNING:
            self.apply_action(command, kwargs.get(ATTR_POSITION, 0))
        else:
            self.apply_action(command, 100 - kwargs.get(ATTR_POSITION, 0))

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._closed

    @property
    def device_class(self):
        """Return the class of the device."""
        return TAHOMA_DEVICE_CLASSES.get(self.tahoma_device.type)

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        super_attr = super().extra_state_attributes
        if super_attr is not None:
            attr.update(super_attr)

        if "core:Memorized1PositionState" in self.tahoma_device.active_states:
            attr[ATTR_MEM_POS] = self.tahoma_device.active_states[
                "core:Memorized1PositionState"
            ]
        if self._rssi_level is not None:
            attr[ATTR_RSSI_LEVEL] = self._rssi_level
        if self._lock_start_ts is not None:
            attr[ATTR_LOCK_START_TS] = self._lock_start_ts.isoformat()
        if self._lock_end_ts is not None:
            attr[ATTR_LOCK_END_TS] = self._lock_end_ts.isoformat()
        if self._lock_level is not None:
            attr[ATTR_LOCK_LEVEL] = self._lock_level
        if self._lock_originator is not None:
            attr[ATTR_LOCK_ORIG] = self._lock_originator
        return attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.apply_action("open")

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.apply_action("close")

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        if (
            self.tahoma_device.type
            == "io:RollerShutterWithLowSpeedManagementIOComponent"
        ):
            self.apply_action("setPosition", "secured")
        elif self.tahoma_device.type in {
            "io:ExteriorVenetianBlindIOComponent",
            "rts:BlindRTSComponent",
            "rts:DualCurtainRTSComponent",
            "rts:ExteriorVenetianBlindRTSComponent",
            "rts:VenetianBlindRTSComponent",
        }:
            self.apply_action("my")
        elif self.tahoma_device.type in {
            HORIZONTAL_AWNING,
            "io:AwningValanceIOComponent",
            "io:RollerShutterGenericIOComponent",
            "io:VerticalExteriorAwningIOComponent",
            "io:VerticalInteriorBlindVeluxIOComponent",
            "io:WindowOpenerVeluxIOComponent",
        }:
            self.apply_action("stop")
        else:
            self.apply_action("stopIdentify")
