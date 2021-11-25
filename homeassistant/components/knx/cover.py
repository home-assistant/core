"""Support for KNX/IP covers."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from xknx import XKNX
from xknx.devices import Cover as XknxCover, Device as XknxDevice

from homeassistant import config_entries
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_BLIND,
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
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ENTITY_CATEGORY, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.typing import ConfigType

from .const import DATA_KNX_CONFIG, DOMAIN, SupportedPlatforms
from .knx_entity import KnxEntity
from .schema import CoverSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover(s) for KNX platform."""
    xknx: XKNX = hass.data[DOMAIN].xknx
    config: list[ConfigType] = hass.data[DATA_KNX_CONFIG][
        SupportedPlatforms.COVER.value
    ]

    async_add_entities(KNXCover(xknx, entity_config) for entity_config in config)


class KNXCover(KnxEntity, CoverEntity):
    """Representation of a KNX cover."""

    _device: XknxCover

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize the cover."""
        super().__init__(
            device=XknxCover(
                xknx,
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
                invert_position=config[CoverSchema.CONF_INVERT_POSITION],
                invert_angle=config[CoverSchema.CONF_INVERT_ANGLE],
            )
        )
        self._unsubscribe_auto_updater: Callable[[], None] | None = None
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)

        self._attr_device_class = config.get(CONF_DEVICE_CLASS) or (
            DEVICE_CLASS_BLIND if self._device.supports_angle else None
        )
        self._attr_supported_features = (
            SUPPORT_CLOSE | SUPPORT_OPEN | SUPPORT_SET_POSITION
        )
        if self._device.supports_stop:
            self._attr_supported_features |= SUPPORT_STOP | SUPPORT_STOP_TILT
        if self._device.supports_angle:
            self._attr_supported_features |= SUPPORT_SET_TILT_POSITION
        if self._device.step.writable:
            self._attr_supported_features |= (
                SUPPORT_CLOSE_TILT | SUPPORT_OPEN_TILT | SUPPORT_STOP_TILT
            )
        self._attr_unique_id = (
            f"{self._device.updown.group_address}_"
            f"{self._device.position_target.group_address}"
        )

    @callback
    async def after_update_callback(self, device: XknxDevice) -> None:
        """Call after device was updated."""
        self.async_write_ha_state()
        if self._device.is_traveling():
            self.start_auto_updater()

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        # In KNX 0 is open, 100 is closed.
        pos = self._device.current_position()
        return 100 - pos if pos is not None else None

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
        self.stop_auto_updater()

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if not self._device.supports_angle:
            return None
        ang = self._device.current_angle()
        return 100 - ang if ang is not None else None

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        knx_tilt_position = 100 - kwargs[ATTR_TILT_POSITION]
        await self._device.set_angle(knx_tilt_position)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self._device.set_short_up()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self._device.set_short_down()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self._device.stop()
        self.stop_auto_updater()

    def start_auto_updater(self) -> None:
        """Start the autoupdater to update Home Assistant while cover is moving."""
        if self._unsubscribe_auto_updater is None:
            self._unsubscribe_auto_updater = async_track_utc_time_change(
                self.hass, self.auto_updater_hook
            )

    def stop_auto_updater(self) -> None:
        """Stop the autoupdater."""
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    @callback
    def auto_updater_hook(self, now: datetime) -> None:
        """Call for the autoupdater."""
        self.async_write_ha_state()
        if self._device.position_reached():
            self.hass.async_create_task(self._device.auto_stop_if_necessary())
            self.stop_auto_updater()
