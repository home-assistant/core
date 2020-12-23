"""Support for Motion Blinds using their WLAN API."""

import logging

from motionblinds import BlindType

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_AWNING,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_CURTAIN,
    DEVICE_CLASS_GATE,
    DEVICE_CLASS_SHADE,
    DEVICE_CLASS_SHUTTER,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_COORDINATOR, KEY_GATEWAY, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


POSITION_DEVICE_MAP = {
    BlindType.RollerBlind: DEVICE_CLASS_SHADE,
    BlindType.RomanBlind: DEVICE_CLASS_SHADE,
    BlindType.HoneycombBlind: DEVICE_CLASS_SHADE,
    BlindType.DimmingBlind: DEVICE_CLASS_SHADE,
    BlindType.DayNightBlind: DEVICE_CLASS_SHADE,
    BlindType.RollerShutter: DEVICE_CLASS_SHUTTER,
    BlindType.Switch: DEVICE_CLASS_SHUTTER,
    BlindType.RollerGate: DEVICE_CLASS_GATE,
    BlindType.Awning: DEVICE_CLASS_AWNING,
    BlindType.Curtain: DEVICE_CLASS_CURTAIN,
    BlindType.CurtainLeft: DEVICE_CLASS_CURTAIN,
    BlindType.CurtainRight: DEVICE_CLASS_CURTAIN,
}

TILT_DEVICE_MAP = {
    BlindType.VenetianBlind: DEVICE_CLASS_BLIND,
    BlindType.ShangriLaBlind: DEVICE_CLASS_BLIND,
    BlindType.DoubleRoller: DEVICE_CLASS_SHADE,
}

TDBU_DEVICE_MAP = {
    BlindType.TopDownBottomUp: DEVICE_CLASS_SHADE,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Motion Blind from a config entry."""
    entities = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for blind in motion_gateway.device_list.values():
        if blind.type in POSITION_DEVICE_MAP:
            entities.append(
                MotionPositionDevice(
                    coordinator, blind, POSITION_DEVICE_MAP[blind.type], config_entry
                )
            )

        elif blind.type in TILT_DEVICE_MAP:
            entities.append(
                MotionTiltDevice(
                    coordinator, blind, TILT_DEVICE_MAP[blind.type], config_entry
                )
            )

        elif blind.type in TDBU_DEVICE_MAP:
            entities.append(
                MotionTDBUDevice(
                    coordinator, blind, TDBU_DEVICE_MAP[blind.type], config_entry, "Top"
                )
            )
            entities.append(
                MotionTDBUDevice(
                    coordinator,
                    blind,
                    TDBU_DEVICE_MAP[blind.type],
                    config_entry,
                    "Bottom",
                )
            )

        else:
            _LOGGER.warning("Blind type '%s' not yet supported", blind.blind_type)

    async_add_entities(entities)


class MotionPositionDevice(CoordinatorEntity, CoverEntity):
    """Representation of a Motion Blind Device."""

    def __init__(self, coordinator, blind, device_class, config_entry):
        """Initialize the blind."""
        super().__init__(coordinator)

        self._blind = blind
        self._device_class = device_class
        self._config_entry = config_entry

    @property
    def unique_id(self):
        """Return the unique id of the blind."""
        return self._blind.mac

    @property
    def device_info(self):
        """Return the device info of the blind."""
        device_info = {
            "identifiers": {(DOMAIN, self._blind.mac)},
            "manufacturer": MANUFACTURER,
            "name": f"{self._blind.blind_type}-{self._blind.mac[12:]}",
            "model": self._blind.blind_type,
            "via_device": (DOMAIN, self._config_entry.unique_id),
        }

        return device_info

    @property
    def name(self):
        """Return the name of the blind."""
        return f"{self._blind.blind_type}-{self._blind.mac[12:]}"

    @property
    def available(self):
        """Return True if entity is available."""
        return self._blind.available

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is open, 100 is closed.
        """
        if self._blind.position is None:
            return None
        return 100 - self._blind.position

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._blind.position == 100

    @callback
    def _push_callback(self):
        """Update entity state when a push has been received."""
        self.schedule_update_ha_state(force_refresh=False)

    async def async_added_to_hass(self):
        """Subscribe to multicast pushes."""
        self._blind.Register_callback(self.unique_id, self._push_callback)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._blind.Remove_callback(self.unique_id)
        await super().async_will_remove_from_hass()

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._blind.Open()

    def close_cover(self, **kwargs):
        """Close cover."""
        self._blind.Close()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        self._blind.Set_position(100 - position)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop()


class MotionTiltDevice(MotionPositionDevice):
    """Representation of a Motion Blind Device."""

    @property
    def current_cover_tilt_position(self):
        """
        Return current angle of cover.

        None is unknown, 0 is closed/minimum tilt, 100 is fully open/maximum tilt.
        """
        if self._blind.angle is None:
            return None
        return self._blind.angle * 100 / 180

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self._blind.Set_angle(180)

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self._blind.Set_angle(0)

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        angle = kwargs[ATTR_TILT_POSITION] * 180 / 100
        self._blind.Set_angle(angle)

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop()


class MotionTDBUDevice(MotionPositionDevice):
    """Representation of a Motion Top Down Bottom Up blind Device."""

    def __init__(self, coordinator, blind, device_class, config_entry, motor):
        """Initialize the blind."""
        super().__init__(coordinator, blind, device_class, config_entry)
        self._motor = motor
        self._motor_key = motor[0]

        if self._motor not in ["Bottom", "Top"]:
            _LOGGER.error("Unknown motor '%s'", self._motor)

    @property
    def unique_id(self):
        """Return the unique id of the blind."""
        return f"{self._blind.mac}-{self._motor}"

    @property
    def name(self):
        """Return the name of the blind."""
        return f"{self._blind.blind_type}-{self._motor}-{self._blind.mac[12:]}"

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is open, 100 is closed.
        """
        if self._blind.position is None:
            return None

        return 100 - self._blind.position[self._motor_key]

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            return None

        return self._blind.position[self._motor_key] == 100

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._blind.Open(motor=self._motor_key)

    def close_cover(self, **kwargs):
        """Close cover."""
        self._blind.Close(motor=self._motor_key)

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        self._blind.Set_position(100 - position, motor=self._motor_key)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop(motor=self._motor_key)
