"""Cover Platform for Chacon Dio REV-SHUTTER devices."""

import logging
from typing import Any

from dio_chacon_wifi_api.const import DeviceTypeEnum, ShutterMoveEnum

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ChaconDioConfigEntry
from .entity import ChaconDioEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ChaconDioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Chacon Dio cover devices."""
    data = config_entry.runtime_data
    client = data.client

    async_add_entities(
        ChaconDioCover(client, device)
        for device in data.list_devices
        if device["type"] == DeviceTypeEnum.SHUTTER.value
    )


class ChaconDioCover(ChaconDioEntity, CoverEntity):
    """Object for controlling a Chacon Dio cover."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_name = None

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def _update_attr(self, data: dict[str, Any]) -> None:
        """Recomputes the attributes values either at init or when the device state changes."""
        self._attr_available = data["connected"]
        self._attr_current_cover_position = data["openlevel"]
        self._attr_is_closing = data["movement"] == ShutterMoveEnum.DOWN.value
        self._attr_is_opening = data["movement"] == ShutterMoveEnum.UP.value
        self._attr_is_closed = self._attr_current_cover_position == 0

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover.

        Closed status is effective after the server callback that triggers callback_device_state.
        """

        _LOGGER.debug(
            "Close cover %s , %s, %s",
            self.target_id,
            self._attr_name,
            self.is_closed,
        )

        # closes effectively only if cover is not already closing and not fully closed
        if not self._attr_is_closing and not self.is_closed:
            self._attr_is_closing = True
            self.async_write_ha_state()

            await self.client.move_shutter_direction(
                self.target_id, ShutterMoveEnum.DOWN
            )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover.

        Opened status is effective after the server callback that triggers callback_device_state.
        """

        _LOGGER.debug(
            "Open cover %s , %s, %s",
            self.target_id,
            self._attr_name,
            self.current_cover_position,
        )

        # opens effectively only if cover is not already opening and not fully opened
        if not self._attr_is_opening and self.current_cover_position != 100:
            self._attr_is_opening = True
            self.async_write_ha_state()

            await self.client.move_shutter_direction(self.target_id, ShutterMoveEnum.UP)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""

        _LOGGER.debug("Stop cover %s , %s", self.target_id, self._attr_name)

        self._attr_is_opening = False
        self._attr_is_closing = False
        self.async_write_ha_state()

        await self.client.move_shutter_direction(self.target_id, ShutterMoveEnum.STOP)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover open position in percentage.

        Closing or opening status is effective after the server callback that triggers callback_device_state.
        """
        position: int = kwargs[ATTR_POSITION]

        _LOGGER.debug(
            "Set cover position %i, %s , %s", position, self.target_id, self._attr_name
        )

        await self.client.move_shutter_percentage(self.target_id, position)
