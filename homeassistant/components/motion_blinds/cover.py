"""Support for Motionblinds using their WLAN API."""

from __future__ import annotations

import logging
from typing import Any

from motionblinds import BlindType
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_ABSOLUTE_POSITION,
    ATTR_AVAILABLE,
    ATTR_WIDTH,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_GATEWAY,
    SERVICE_SET_ABSOLUTE_POSITION,
    UPDATE_DELAY_STOP,
)
from .entity import MotionCoordinatorEntity

_LOGGER = logging.getLogger(__name__)


POSITION_DEVICE_MAP = {
    BlindType.RollerBlind: CoverDeviceClass.SHADE,
    BlindType.RomanBlind: CoverDeviceClass.SHADE,
    BlindType.HoneycombBlind: CoverDeviceClass.SHADE,
    BlindType.DimmingBlind: CoverDeviceClass.SHADE,
    BlindType.DayNightBlind: CoverDeviceClass.SHADE,
    BlindType.RollerShutter: CoverDeviceClass.SHUTTER,
    BlindType.Switch: CoverDeviceClass.SHUTTER,
    BlindType.RollerGate: CoverDeviceClass.GATE,
    BlindType.Awning: CoverDeviceClass.AWNING,
    BlindType.Curtain: CoverDeviceClass.CURTAIN,
    BlindType.CurtainLeft: CoverDeviceClass.CURTAIN,
    BlindType.CurtainRight: CoverDeviceClass.CURTAIN,
    BlindType.SkylightBlind: CoverDeviceClass.SHADE,
    BlindType.InsectScreen: CoverDeviceClass.SHADE,
}

TILT_DEVICE_MAP = {
    BlindType.VenetianBlind: CoverDeviceClass.BLIND,
    BlindType.ShangriLaBlind: CoverDeviceClass.BLIND,
    BlindType.DoubleRoller: CoverDeviceClass.SHADE,
    BlindType.DualShade: CoverDeviceClass.SHADE,
    BlindType.VerticalBlind: CoverDeviceClass.BLIND,
    BlindType.VerticalBlindLeft: CoverDeviceClass.BLIND,
    BlindType.VerticalBlindRight: CoverDeviceClass.BLIND,
}

TILT_ONLY_DEVICE_MAP = {
    BlindType.WoodShutter: CoverDeviceClass.BLIND,
}

TDBU_DEVICE_MAP = {
    BlindType.TopDownBottomUp: CoverDeviceClass.SHADE,
    BlindType.TriangleBlind: CoverDeviceClass.BLIND,
}


SET_ABSOLUTE_POSITION_SCHEMA: VolDictType = {
    vol.Required(ATTR_ABSOLUTE_POSITION): vol.All(cv.positive_int, vol.Range(max=100)),
    vol.Optional(ATTR_TILT_POSITION): vol.All(cv.positive_int, vol.Range(max=100)),
    vol.Optional(ATTR_WIDTH): vol.All(cv.positive_int, vol.Range(max=100)),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Motion Blind from a config entry."""
    entities: list[MotionBaseDevice] = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for blind in motion_gateway.device_list.values():
        if blind.type in POSITION_DEVICE_MAP:
            entities.append(
                MotionPositionDevice(
                    coordinator,
                    blind,
                    POSITION_DEVICE_MAP[blind.type],
                )
            )

        elif blind.type in TILT_DEVICE_MAP:
            entities.append(
                MotionTiltDevice(
                    coordinator,
                    blind,
                    TILT_DEVICE_MAP[blind.type],
                )
            )

        elif blind.type in TILT_ONLY_DEVICE_MAP:
            entities.append(
                MotionTiltOnlyDevice(
                    coordinator,
                    blind,
                    TILT_ONLY_DEVICE_MAP[blind.type],
                )
            )

        elif blind.type in TDBU_DEVICE_MAP:
            entities.append(
                MotionTDBUDevice(
                    coordinator,
                    blind,
                    TDBU_DEVICE_MAP[blind.type],
                    "Top",
                )
            )
            entities.append(
                MotionTDBUDevice(
                    coordinator,
                    blind,
                    TDBU_DEVICE_MAP[blind.type],
                    "Bottom",
                )
            )
            entities.append(
                MotionTDBUDevice(
                    coordinator,
                    blind,
                    TDBU_DEVICE_MAP[blind.type],
                    "Combined",
                )
            )

        else:
            _LOGGER.warning(
                "Blind type '%s' not yet supported, assuming RollerBlind",
                blind.blind_type,
            )
            entities.append(
                MotionPositionDevice(
                    coordinator,
                    blind,
                    POSITION_DEVICE_MAP[BlindType.RollerBlind],
                )
            )

    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_ABSOLUTE_POSITION,
        SET_ABSOLUTE_POSITION_SCHEMA,
        "async_set_absolute_position",
    )


class MotionBaseDevice(MotionCoordinatorEntity, CoverEntity):
    """Representation of a Motionblinds Device."""

    _restore_tilt = False

    def __init__(self, coordinator, blind, device_class):
        """Initialize the blind."""
        super().__init__(coordinator, blind)

        self._attr_device_class = device_class
        self._attr_unique_id = blind.mac

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.coordinator.data is None:
            return False

        if not self.coordinator.data[KEY_GATEWAY][ATTR_AVAILABLE]:
            return False

        return self.coordinator.data[self._blind.mac][ATTR_AVAILABLE]

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is open, 100 is closed.
        """
        if self._blind.position is None:
            return None
        return 100 - self._blind.position

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            return None
        return self._blind.position == 100

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Open)
        await self.async_request_position_till_stop()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Close)
        await self.async_request_position_till_stop()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._blind.Set_position,
                100 - position,
                None,
                self._restore_tilt,
            )
        await self.async_request_position_till_stop()

    async def async_set_absolute_position(self, **kwargs):
        """Move the cover to a specific absolute position (see TDBU)."""
        position = kwargs[ATTR_ABSOLUTE_POSITION]
        angle = kwargs.get(ATTR_TILT_POSITION)
        if angle is not None:
            angle = angle * 180 / 100
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._blind.Set_position,
                100 - position,
                angle,
                self._restore_tilt,
            )
        await self.async_request_position_till_stop()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Stop)

        await self.async_request_position_till_stop(delay=UPDATE_DELAY_STOP)


class MotionPositionDevice(MotionBaseDevice):
    """Representation of a Motion Blind Device."""

    _attr_name = None


class MotionTiltDevice(MotionPositionDevice):
    """Representation of a Motionblinds Device."""

    _restore_tilt = True

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current angle of cover.

        None is unknown, 0 is closed/minimum tilt, 100 is fully open/maximum tilt.
        """
        if self._blind.angle is None:
            return None
        return self._blind.angle * 100 / 180

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            return None
        return self._blind.position >= 95

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Set_angle, 180)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Set_angle, 0)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        angle = kwargs[ATTR_TILT_POSITION] * 180 / 100
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Set_angle, angle)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Stop)

        await self.async_request_position_till_stop(delay=UPDATE_DELAY_STOP)


class MotionTiltOnlyDevice(MotionTiltDevice):
    """Representation of a Motionblinds Device."""

    _restore_tilt = False

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        supported_features = (
            CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.STOP_TILT
        )

        if self.current_cover_tilt_position is not None:
            supported_features |= CoverEntityFeature.SET_TILT_POSITION

        return supported_features

    @property
    def current_cover_position(self) -> None:
        """Return current position of cover."""
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current angle of cover.

        None is unknown, 0 is closed/minimum tilt, 100 is fully open/maximum tilt.
        """
        if self._blind.position is None:
            if self._blind.angle is None:
                return None
            return self._blind.angle * 100 / 180

        return self._blind.position

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            if self._blind.angle is None:
                return None
            return self._blind.angle == 0

        return self._blind.position == 0

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Open)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Close)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        angle = kwargs[ATTR_TILT_POSITION]
        if self._blind.position is None:
            angle = angle * 180 / 100
            async with self._api_lock:
                await self.hass.async_add_executor_job(self._blind.Set_angle, angle)
        else:
            async with self._api_lock:
                await self.hass.async_add_executor_job(self._blind.Set_position, angle)

    async def async_set_absolute_position(self, **kwargs):
        """Move the cover to a specific absolute position (see TDBU)."""
        angle = kwargs.get(ATTR_TILT_POSITION)
        if angle is None:
            return

        if self._blind.position is None:
            angle = angle * 180 / 100
            async with self._api_lock:
                await self.hass.async_add_executor_job(self._blind.Set_angle, angle)
        else:
            async with self._api_lock:
                await self.hass.async_add_executor_job(self._blind.Set_position, angle)


class MotionTDBUDevice(MotionBaseDevice):
    """Representation of a Motion Top Down Bottom Up blind Device."""

    def __init__(self, coordinator, blind, device_class, motor):
        """Initialize the blind."""
        super().__init__(coordinator, blind, device_class)
        self._motor = motor
        self._motor_key = motor[0]
        self._attr_translation_key = motor.lower()
        self._attr_unique_id = f"{blind.mac}-{motor}"

        if self._motor not in ["Bottom", "Top", "Combined"]:
            _LOGGER.error("Unknown motor '%s'", self._motor)

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is open, 100 is closed.
        """
        if self._blind.scaled_position is None:
            return None

        return 100 - self._blind.scaled_position[self._motor_key]

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._blind.position is None:
            return None

        if self._motor == "Combined":
            return self._blind.width == 100

        return self._blind.position[self._motor_key] == 100

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        attributes = {}
        if self._blind.position is not None:
            attributes[ATTR_ABSOLUTE_POSITION] = (
                100 - self._blind.position[self._motor_key]
            )
        if self._blind.width is not None:
            attributes[ATTR_WIDTH] = self._blind.width
        return attributes

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Open, self._motor_key)
        await self.async_request_position_till_stop()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Close, self._motor_key)
        await self.async_request_position_till_stop()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific scaled position."""
        position = kwargs[ATTR_POSITION]
        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._blind.Set_scaled_position, 100 - position, self._motor_key
            )
        await self.async_request_position_till_stop()

    async def async_set_absolute_position(self, **kwargs):
        """Move the cover to a specific absolute position."""
        position = kwargs[ATTR_ABSOLUTE_POSITION]
        target_width = kwargs.get(ATTR_WIDTH)

        async with self._api_lock:
            await self.hass.async_add_executor_job(
                self._blind.Set_position, 100 - position, self._motor_key, target_width
            )

        await self.async_request_position_till_stop()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        async with self._api_lock:
            await self.hass.async_add_executor_job(self._blind.Stop, self._motor_key)

        await self.async_request_position_till_stop(delay=UPDATE_DELAY_STOP)
