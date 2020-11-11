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

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Motion Blind from a config entry."""
    entities = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id]
    for blind in motion_gateway.device_list.values():
        await hass.async_add_executor_job(blind.Update)

        if blind.type in [
            BlindType.RollerBlind,
            BlindType.RomanBlind,
            BlindType.HoneycombBlind,
            BlindType.DimmingBlind,
            BlindType.DayNightBlind,
        ]:
            entities.append(
                MotionPositionDevice(blind, DEVICE_CLASS_SHADE, config_entry)
            )

        elif blind.type in [
            BlindType.RollerShutter,
            BlindType.Switch,
        ]:
            entities.append(
                MotionPositionDevice(blind, DEVICE_CLASS_SHUTTER, config_entry)
            )

        elif blind.type in [BlindType.RollerGate]:
            entities.append(
                MotionPositionDevice(blind, DEVICE_CLASS_GATE, config_entry)
            )

        elif blind.type in [BlindType.Awning]:
            entities.append(
                MotionPositionDevice(blind, DEVICE_CLASS_AWNING, config_entry)
            )

        elif blind.type in [
            BlindType.Curtain,
            BlindType.CurtainLeft,
            BlindType.CurtainRight,
        ]:
            entities.append(
                MotionPositionDevice(blind, DEVICE_CLASS_CURTAIN, config_entry)
            )

        elif blind.type in [
            BlindType.VenetianBlind,
            BlindType.ShangriLaBlind,
        ]:
            entities.append(MotionTiltDevice(blind, DEVICE_CLASS_BLIND, config_entry))

        elif blind.type in [BlindType.DoubleRoller]:
            entities.append(MotionTiltDevice(blind, DEVICE_CLASS_SHADE, config_entry))

        elif blind.type in [BlindType.TopDownBottomUp]:
            entities.append(
                MotionTDBUDevice(blind, DEVICE_CLASS_SHADE, config_entry, "Top")
            )
            entities.append(
                MotionTDBUDevice(blind, DEVICE_CLASS_SHADE, config_entry, "Bottom")
            )

        else:
            _LOGGER.warning("Blind type '%s' not yet supported", blind.blind_type)

    async_add_entities(entities)


class MotionPositionDevice(CoverEntity):
    """Representation of a Motion Blind Device."""

    def __init__(self, blind, device_class, config_entry):
        """Initialize the blind."""
        self._blind = blind
        self._device_class = device_class
        self._config_entry = config_entry

    def update(self):
        """Get the latest status information from blind."""
        self._blind.Update()

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
            "name": f"{self._blind.blind_type}-{self._blind.mac}",
            "model": self._blind.blind_type,
            "via_device": (DOMAIN, self._config_entry.unique_id),
        }

        return device_info

    @property
    def name(self):
        """Return the name of the blind."""
        return f"{self._blind.blind_type}-{self._blind.mac}"

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

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._blind.Open()

    def close_cover(self, **kwargs):
        """Close cover."""
        self._blind.Close()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
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
        if ATTR_TILT_POSITION in kwargs:
            angle = kwargs[ATTR_TILT_POSITION] * 180 / 100
            self._blind.Set_angle(angle)

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop()


class MotionTDBUDevice(MotionPositionDevice):
    """Representation of a Motion Top Down Bottom Up blind Device."""

    def __init__(self, blind, device_class, config_entry, motor):
        """Initialize the blind."""
        super().__init__(blind, device_class, config_entry)
        self._motor = motor

    def update(self):
        """
        Get the latest status information from blind.

        Top motor is being updated by the Bottom entity
        """
        if self._motor == "Bottom":
            self._blind.Update()

    @property
    def unique_id(self):
        """Return the unique id of the blind."""
        return f"{self._blind.mac}-{self._motor}"

    @property
    def name(self):
        """Return the name of the blind."""
        return f"{self._blind.blind_type}-{self._motor}-{self._blind.mac}"

    @property
    def current_cover_position(self):
        """
        Return current position of cover.

        None is unknown, 0 is open, 100 is closed.
        """
        if self._blind.position is None:
            return None

        if self._motor == "Bottom":
            return 100 - self._blind.position["B"]

        if self._motor == "Top":
            return 100 - self._blind.position["T"]

        _LOGGER.error("Unknown motor '%s'", self._motor)
        return None

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            return None

        if self._motor == "Bottom":
            return self._blind.position["B"] == 100

        if self._motor == "Top":
            return self._blind.position["T"] == 100

        _LOGGER.error("Unknown motor '%s'", self._motor)
        return None

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._blind.Open(motor=self._motor[0])

    def close_cover(self, **kwargs):
        """Close cover."""
        self._blind.Close(motor=self._motor[0])

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            self._blind.Set_position(100 - position, motor=self._motor[0])

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._blind.Stop(motor=self._motor[0])
