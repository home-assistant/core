"""Support for KNX/IP covers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from xknx.devices import Cover as XknxCover

from homeassistant import config_entries
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import KNXModule
from .const import KNX_MODULE_KEY
from .entity import KnxYamlEntity
from .schema import CoverSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cover(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    config: list[ConfigType] = knx_module.config_yaml[Platform.COVER]

    async_add_entities(KNXCover(knx_module, entity_config) for entity_config in config)


class KNXCover(KnxYamlEntity, CoverEntity):
    """Representation of a KNX cover."""

    _device: XknxCover

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize the cover."""
        super().__init__(
            knx_module=knx_module,
            device=XknxCover(
                xknx=knx_module.xknx,
                name=config[CONF_NAME],
                group_address_long=config.get(CoverSchema.CONF_MOVE_LONG_ADDRESS),
                group_address_short=config.get(CoverSchema.CONF_MOVE_SHORT_ADDRESS),
                group_address_stop=config.get(CoverSchema.CONF_STOP_ADDRESS),
                group_address_position_state=config.get(
                    CoverSchema.CONF_POSITION_STATE_ADDRESS
                ),
                group_address_angle=config.get(CoverSchema.CONF_ANGLE_ADDRESS),
                group_address_angle_state=config.get(
                    CoverSchema.CONF_ANGLE_STATE_ADDRESS
                ),
                group_address_position=config.get(CoverSchema.CONF_POSITION_ADDRESS),
                travel_time_down=config[CoverSchema.CONF_TRAVELLING_TIME_DOWN],
                travel_time_up=config[CoverSchema.CONF_TRAVELLING_TIME_UP],
                invert_updown=config[CoverSchema.CONF_INVERT_UPDOWN],
                invert_position=config[CoverSchema.CONF_INVERT_POSITION],
                invert_angle=config[CoverSchema.CONF_INVERT_ANGLE],
            ),
        )
        self._unsubscribe_auto_updater: Callable[[], None] | None = None

        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        _supports_tilt = False
        self._attr_supported_features = (
            CoverEntityFeature.CLOSE
            | CoverEntityFeature.OPEN
            | CoverEntityFeature.SET_POSITION
        )
        if self._device.step.writable:
            _supports_tilt = True
            self._attr_supported_features |= (
                CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.STOP_TILT
            )
        if self._device.supports_angle:
            _supports_tilt = True
            self._attr_supported_features |= CoverEntityFeature.SET_TILT_POSITION
        if self._device.supports_stop:
            self._attr_supported_features |= CoverEntityFeature.STOP
            if _supports_tilt:
                self._attr_supported_features |= CoverEntityFeature.STOP_TILT

        self._attr_device_class = config.get(CONF_DEVICE_CLASS) or (
            CoverDeviceClass.BLIND if _supports_tilt else None
        )
        self._attr_unique_id = (
            f"{self._device.updown.group_address}_"
            f"{self._device.position_target.group_address}"
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        # In KNX 0 is open, 100 is closed.
        if (pos := self._device.current_position()) is not None:
            return 100 - pos
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        # state shall be "unknown" when xknx travelcalculator is not initialized
        if self._device.current_position() is None:
            return None
        return self._device.is_closed()

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._device.is_opening()

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._device.is_closing()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._device.set_down()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._device.set_up()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        knx_position = 100 - kwargs[ATTR_POSITION]
        await self._device.set_position(knx_position)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._device.stop()

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if (angle := self._device.current_angle()) is not None:
            return 100 - angle
        return None

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        knx_tilt_position = 100 - kwargs[ATTR_TILT_POSITION]
        await self._device.set_angle(knx_tilt_position)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if self._device.angle.writable:
            await self._device.set_angle(0)
        else:
            await self._device.set_short_up()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if self._device.angle.writable:
            await self._device.set_angle(100)
        else:
            await self._device.set_short_down()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self._device.stop()
