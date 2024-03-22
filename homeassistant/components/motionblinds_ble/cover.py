"""Cover entities for the Motionblinds BLE integration."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, kw_only=True)
class MotionblindsBLECoverEntityDescription(CoverEntityDescription):
    """Entity description of a cover entity with default values."""

    key: str = CoverDeviceClass.BLIND.value
    translation_key: str = CoverDeviceClass.BLIND.value


SHADE_ENTITY_DESCRIPTION = MotionblindsBLECoverEntityDescription(
    device_class=CoverDeviceClass.SHADE
)
BLIND_ENTITY_DESCRIPTION = MotionblindsBLECoverEntityDescription(
    device_class=CoverDeviceClass.BLIND
)
CURTAIN_ENTITY_DESCRIPTION = MotionblindsBLECoverEntityDescription(
    device_class=CoverDeviceClass.CURTAIN
)
VERTICAL_ENTITY_DESCRIPTION = MotionblindsBLECoverEntityDescription(
    device_class=CoverDeviceClass.CURTAIN, icon=ICON_VERTICAL_BLIND
)

BLIND_TYPE_TO_ENTITY_DESCRIPTION: dict[str, MotionblindsBLECoverEntityDescription] = {
    MotionBlindType.HONEYCOMB.name: SHADE_ENTITY_DESCRIPTION,
    MotionBlindType.ROMAN.name: SHADE_ENTITY_DESCRIPTION,
    MotionBlindType.ROLLER.name: SHADE_ENTITY_DESCRIPTION,
    MotionBlindType.DOUBLE_ROLLER.name: SHADE_ENTITY_DESCRIPTION,
    MotionBlindType.VENETIAN.name: BLIND_ENTITY_DESCRIPTION,
    MotionBlindType.VENETIAN_TILT_ONLY.name: BLIND_ENTITY_DESCRIPTION,
    MotionBlindType.CURTAIN.name: CURTAIN_ENTITY_DESCRIPTION,
    MotionBlindType.VERTICAL.name: VERTICAL_ENTITY_DESCRIPTION,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up blind based on a config entry."""

    blind_class: type[MotionblindsBLECoverEntity] = BLIND_TYPE_TO_CLASS[
        entry.data[CONF_BLIND_TYPE].upper()
    ]
    device: MotionDevice = hass.data[DOMAIN][entry.entry_id]
    entity_description: MotionblindsBLECoverEntityDescription = (
        BLIND_TYPE_TO_ENTITY_DESCRIPTION[entry.data[CONF_BLIND_TYPE].upper()]
    )
    entity = blind_class(device, entry, entity_description)

    async_add_entities([entity])


class MotionblindsBLECoverEntity(MotionblindsBLEEntity, CoverEntity):
    """Representation of a blind."""

    _attr_is_closed: bool | None = None
    _attr_name = None

    async def async_added_to_hass(self) -> None:
        """Register device callbacks."""
        _LOGGER.debug(
            "(%s) Added %s cover entity (%s)",
            self.entry.data[CONF_MAC_CODE],
            MotionBlindType[self.entry.data[CONF_BLIND_TYPE].upper()].value.lower(),
            BLIND_TYPE_TO_CLASS[self.entry.data[CONF_BLIND_TYPE].upper()].__name__,
        )
        self.device.register_running_callback(self.async_update_running)
        self.device.register_position_callback(self.async_update_position)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop moving the blind."""
        _LOGGER.debug("(%s) Stopping", self.entry.data[CONF_MAC_CODE])
        await self.device.stop()

    @callback
    def async_update_running(
        self, running_type: MotionRunningType | None, write_state: bool = True
    ) -> None:
        """Update whether the blind is running (opening/closing) or not."""
        if running_type in {None, MotionRunningType.STILL, MotionRunningType.UNKNOWN}:
            self._attr_is_opening = False
            self._attr_is_closing = False
        else:
            self._attr_is_opening = running_type is MotionRunningType.OPENING
            self._attr_is_closing = running_type is not MotionRunningType.OPENING
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
        if position is None:
            self._attr_current_cover_position = None
            self._attr_is_closed = None
        else:
            self._attr_current_cover_position = 100 - position
            self._attr_is_closed = self._attr_current_cover_position == 0
        if tilt is None:
            self._attr_current_cover_tilt_position = None
        else:
            self._attr_current_cover_tilt_position = 100 - round(100 * tilt / 180)
        self.async_write_ha_state()


class PositionBlind(MotionblindsBLECoverEntity):
    """Representation of a blind with position capability."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the blind."""
        _LOGGER.debug("(%s) Opening", self.entry.data[CONF_MAC_CODE])
        await self.device.open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the blind."""
        _LOGGER.debug("(%s) Closing", self.entry.data[CONF_MAC_CODE])
        await self.device.close()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the blind to a specific position."""
        new_position: int = 100 - int(kwargs[ATTR_POSITION])

        _LOGGER.debug(
            "(%s) Setting position to %i",
            self.entry.data[CONF_MAC_CODE],
            new_position,
        )
        await self.device.position(new_position)


class TiltBlind(MotionblindsBLECoverEntity):
    """Representation of a blind with tilt capability."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the blind open."""
        _LOGGER.debug("(%s) Tilt opening", self.entry.data[CONF_MAC_CODE])
        await self.device.open_tilt()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt the blind closed."""
        _LOGGER.debug("(%s) Tilt closing", self.entry.data[CONF_MAC_CODE])
        await self.device.close_tilt()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop tilting the blind."""
        await self.async_stop_cover(**kwargs)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Tilt the blind to a specific position."""
        new_tilt: int = 100 - int(kwargs[ATTR_TILT_POSITION])

        _LOGGER.debug(
            "(%s) Setting tilt position to %i",
            self.entry.data[CONF_MAC_CODE],
            new_tilt,
        )
        await self.device.tilt(round(180 * new_tilt / 100))


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


BLIND_TYPE_TO_CLASS: dict[str, type[MotionblindsBLECoverEntity]] = {
    MotionBlindType.ROLLER.name: PositionBlind,
    MotionBlindType.HONEYCOMB.name: PositionBlind,
    MotionBlindType.ROMAN.name: PositionBlind,
    MotionBlindType.VENETIAN.name: PositionTiltBlind,
    MotionBlindType.VENETIAN_TILT_ONLY.name: TiltBlind,
    MotionBlindType.DOUBLE_ROLLER.name: PositionTiltBlind,
    MotionBlindType.CURTAIN.name: PositionBlind,
    MotionBlindType.VERTICAL.name: PositionTiltBlind,
}
