"""Cover entities for the Motionblinds BLE integration."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

from motionblindsble.const import MotionBlindType, MotionRunningType
from motionblindsble.device import MotionDevice

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BLIND_TYPE, CONF_MAC_CODE, DOMAIN, ICON_VERTICAL_BLIND
from .entity import MotionblindsBLEEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MotionCoverEntityDescription(CoverEntityDescription):
    """Entity description of a cover entity with default values."""

    key: str = field(default=CoverDeviceClass.BLIND.value, init=False)
    translation_key: str = field(default=CoverDeviceClass.BLIND.value, init=False)
    device_class: CoverDeviceClass = field(default=CoverDeviceClass.SHADE, init=True)


COVER_TYPES: dict[str, MotionCoverEntityDescription] = {
    MotionBlindType.ROLLER.name: MotionCoverEntityDescription(),
    MotionBlindType.HONEYCOMB.name: MotionCoverEntityDescription(),
    MotionBlindType.ROMAN.name: MotionCoverEntityDescription(),
    MotionBlindType.VENETIAN.name: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.BLIND
    ),
    MotionBlindType.VENETIAN_TILT_ONLY.name: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.BLIND
    ),
    MotionBlindType.DOUBLE_ROLLER.name: MotionCoverEntityDescription(),
    MotionBlindType.CURTAIN.name: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.CURTAIN
    ),
    MotionBlindType.VERTICAL.name: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.CURTAIN, icon=ICON_VERTICAL_BLIND
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up blind based on a config entry."""

    blind_class = BLIND_TYPE_TO_CLASS[entry.data[CONF_BLIND_TYPE]]
    device = hass.data[DOMAIN][entry.entry_id]
    entity = blind_class(device, entry)

    async_add_entities([entity])


class GenericBlind(MotionblindsBLEEntity, CoverEntity):
    """Representation of a blind."""

    _attr_is_closed: bool | None = None
    _attr_name = None

    def __init__(self, device: MotionDevice, entry: ConfigEntry) -> None:
        """Initialize the blind."""
        _LOGGER.debug(
            "(%s) Setting up %s cover entity (%s)",
            entry.data[CONF_MAC_CODE],
            entry.data[CONF_BLIND_TYPE],
            BLIND_TYPE_TO_CLASS[entry.data[CONF_BLIND_TYPE]].__name__,
        )
        MotionblindsBLEEntity.__init__(self, device, entry)
        CoverEntity.__init__(self)
        self.entity_description = COVER_TYPES[entry.data[CONF_BLIND_TYPE]]
        self._device.register_running_callback(self.async_update_running)
        self._device.register_position_callback(self.async_update_position)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop moving the blind."""
        _LOGGER.debug("(%s) Stopping", self.config_entry.data[CONF_MAC_CODE])
        await self._device.stop()

    @callback
    def async_update_running(
        self, running_type: MotionRunningType | None, write_state: bool = True
    ) -> None:
        """Update whether the blind is running (opening/closing) or not."""
        self._attr_is_opening = (
            False
            if running_type
            in [None, MotionRunningType.STILL, MotionRunningType.UNKNOWN]
            else running_type is MotionRunningType.OPENING
        )
        self._attr_is_closing = (
            False
            if running_type
            in [None, MotionRunningType.STILL, MotionRunningType.UNKNOWN]
            else running_type is not MotionRunningType.OPENING
        )
        if running_type is not MotionRunningType.STILL:
            self._attr_is_closed = None
        if write_state:
            self.async_write_ha_state()

    @callback
    def async_update_position(
        self,
        position: int | None,
        tilt: int | None,
    ) -> None:
        """Update the position of the motor."""
        self._attr_current_cover_position = (
            100 - position if position is not None else None
        )
        self._attr_current_cover_tilt_position = (
            100 - round(100 * tilt / 180) if tilt is not None else None
        )
        self._attr_is_closed = (
            self._attr_current_cover_position == 0 if position is not None else None
        )
        self.async_write_ha_state()


class PositionBlind(GenericBlind):
    """Representation of a blind with position capability."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the blind."""
        _LOGGER.debug("(%s) Opening", self.config_entry.data[CONF_MAC_CODE])
        await self._device.open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the blind."""
        _LOGGER.debug("(%s) Closing", self.config_entry.data[CONF_MAC_CODE])
        await self._device.close()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the blind to a specific position."""
        if kwargs.get(ATTR_POSITION) is None:
            return
        new_position: int = 100 - int(kwargs[ATTR_POSITION])

        _LOGGER.debug(
            "(%s) Setting position to %i",
            self.config_entry.data[CONF_MAC_CODE],
            new_position,
        )
        await self._device.position(new_position)


class TiltBlind(GenericBlind):
    """Representation of a blind with tilt capability."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the blind open."""
        _LOGGER.debug("(%s) Tilt opening", self.config_entry.data[CONF_MAC_CODE])
        await self._device.open_tilt()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the blind closed."""
        _LOGGER.debug("(%s) Tilt closing", self.config_entry.data[CONF_MAC_CODE])
        await self._device.close_tilt()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop tilting the blind."""
        await self.async_stop_cover(**kwargs)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Tilt the blind to a specific position."""
        if kwargs.get(ATTR_TILT_POSITION) is None:
            return
        new_tilt: int = 100 - int(kwargs[ATTR_TILT_POSITION])

        _LOGGER.debug(
            "(%s) Setting tilt position to %i",
            self.config_entry.data[CONF_MAC_CODE],
            new_tilt,
        )
        await self._device.tilt(round(180 * new_tilt / 100))


class PositionTiltBlind(PositionBlind, TiltBlind):
    """Representation of a blind with position & tilt capabilities."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )


BLIND_TYPE_TO_CLASS: dict[str, type[GenericBlind]] = {
    MotionBlindType.ROLLER.name: PositionBlind,
    MotionBlindType.HONEYCOMB.name: PositionBlind,
    MotionBlindType.ROMAN.name: PositionBlind,
    MotionBlindType.VENETIAN.name: PositionTiltBlind,
    MotionBlindType.VENETIAN_TILT_ONLY.name: TiltBlind,
    MotionBlindType.DOUBLE_ROLLER.name: PositionTiltBlind,
    MotionBlindType.CURTAIN.name: PositionBlind,
    MotionBlindType.VERTICAL.name: PositionTiltBlind,
}
