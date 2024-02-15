"""Cover entities for the Motionblinds BLE integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import logging
from typing import Any

from motionblindsble.const import (
    MotionBlindType,
    MotionConnectionType,
    MotionRunningType,
)
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
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CONNECTION,
    CONF_BLIND_TYPE,
    CONF_MAC_CODE,
    DOMAIN,
    ICON_VERTICAL_BLIND,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MotionCoverEntityDescription(CoverEntityDescription):
    """Entity description of a cover entity with default values."""

    key: str = field(default=CoverDeviceClass.BLIND.value, init=False)
    translation_key: str = field(default=CoverDeviceClass.BLIND.value, init=False)
    device_class: CoverDeviceClass = field(default=CoverDeviceClass.SHADE, init=True)


COVER_TYPES: dict[str, MotionCoverEntityDescription] = {
    MotionBlindType.ROLLER.value: MotionCoverEntityDescription(),
    MotionBlindType.HONEYCOMB.value: MotionCoverEntityDescription(),
    MotionBlindType.ROMAN.value: MotionCoverEntityDescription(),
    MotionBlindType.VENETIAN.value: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.BLIND
    ),
    MotionBlindType.VENETIAN_TILT_ONLY.value: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.BLIND
    ),
    MotionBlindType.DOUBLE_ROLLER.value: MotionCoverEntityDescription(),
    MotionBlindType.CURTAIN.value: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.CURTAIN
    ),
    MotionBlindType.VERTICAL.value: MotionCoverEntityDescription(
        device_class=CoverDeviceClass.CURTAIN, icon=ICON_VERTICAL_BLIND
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up blind based on a config entry."""

    blind_type = BLIND_TO_ENTITY_TYPE[entry.data[CONF_BLIND_TYPE]]
    device = hass.data[DOMAIN][entry.entry_id]
    blind = blind_type(device, entry)

    async_add_entities([blind])


class GenericBlind(CoverEntity):
    """Representation of a blind."""

    _attr_should_poll: bool = False

    _device: MotionDevice

    def __init__(self, device: MotionDevice, entry: ConfigEntry) -> None:
        """Initialize the blind."""
        _LOGGER.debug(
            "(%s) Setting up %s cover entity (%s)",
            entry.data[CONF_MAC_CODE],
            entry.data[CONF_BLIND_TYPE],
            BLIND_TO_ENTITY_TYPE[entry.data[CONF_BLIND_TYPE]].__name__,
        )
        super().__init__()
        self._device = device
        self._device.register_running_callback(self.async_update_running)
        self._device.register_position_callback(self.async_update_position)
        self._device.register_connection_callback(self.async_update_connection)
        self.entity_description = COVER_TYPES[entry.data[CONF_BLIND_TYPE]]
        self.config_entry: ConfigEntry = entry

        self._attr_name: str = device.display_name
        self._attr_unique_id: str = entry.data[CONF_ADDRESS]
        self._attr_device_info: DeviceInfo = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_ADDRESS])},
            manufacturer=MANUFACTURER,
            model=entry.data[CONF_BLIND_TYPE],
            name=self._attr_name,
        )

    async def async_update(self) -> None:
        """Update state, called by HA if there is a poll interval and by the service homeassistant.update_entity."""
        _LOGGER.debug("(%s) Updating entity", self.config_entry.data[CONF_MAC_CODE])
        await self._device.connect()

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
        position: int,
        tilt: int,
    ) -> None:
        """Update the position of the motor."""
        self._attr_current_cover_position = 100 - position
        self._attr_current_cover_tilt_position = 100 - round(100 * tilt / 180)
        self._attr_is_closed = self._attr_current_cover_position == 0
        self.async_write_ha_state()

    @callback
    def async_update_connection(self, connection_type: MotionConnectionType) -> None:
        """Update the connection status."""
        if connection_type is MotionConnectionType.DISCONNECTED:
            self._attr_current_cover_position = None
            self._attr_current_cover_tilt_position = None

        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> Mapping[str, str]:
        """Return the state attributes."""
        return {ATTR_CONNECTION: self._device.connection_type}


class PositionBlind(GenericBlind):
    """Representation of a blind with position capability."""

    _attr_supported_features: CoverEntityFeature | None = (
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
        new_position: int | None = (
            100 - int(kwargs[ATTR_POSITION])
            if ATTR_POSITION in kwargs and kwargs[ATTR_POSITION] is not None
            else None
        )
        if new_position is None:
            return

        _LOGGER.debug(
            "(%s) Setting position to %i",
            self.config_entry.data[CONF_MAC_CODE],
            new_position,
        )
        await self._device.position(new_position)


class TiltBlind(GenericBlind):
    """Representation of a blind with tilt capability."""

    _attr_supported_features: CoverEntityFeature | None = (
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
        new_tilt: int | None = (
            100 - int(kwargs[ATTR_TILT_POSITION])
            if ATTR_TILT_POSITION in kwargs and kwargs[ATTR_TILT_POSITION] is not None
            else None
        )
        if new_tilt is None:
            return

        _LOGGER.debug(
            "(%s) Setting tilt position to %i",
            self.config_entry.data[CONF_MAC_CODE],
            new_tilt,
        )
        await self._device.tilt(round(180 * new_tilt / 100))


class PositionTiltBlind(PositionBlind, TiltBlind):
    """Representation of a blind with position & tilt capabilities."""

    _attr_supported_features: CoverEntityFeature | None = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )


BLIND_TO_ENTITY_TYPE: dict[str, type[GenericBlind]] = {
    MotionBlindType.ROLLER.value: PositionBlind,
    MotionBlindType.HONEYCOMB.value: PositionBlind,
    MotionBlindType.ROMAN.value: PositionBlind,
    MotionBlindType.VENETIAN.value: PositionTiltBlind,
    MotionBlindType.VENETIAN_TILT_ONLY.value: TiltBlind,
    MotionBlindType.DOUBLE_ROLLER.value: PositionTiltBlind,
    MotionBlindType.CURTAIN.value: PositionBlind,
    MotionBlindType.VERTICAL.value: PositionTiltBlind,
}
