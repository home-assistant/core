"""Cover Platform for Dio Chacon REV-SHUTTER devices."""

import logging
from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient
from dio_chacon_wifi_api.const import DeviceTypeEnum, ShutterMoveEnum

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DioChaconData
from .entity import DioChaconEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    dio_chacon_data: DioChaconData = config_entry.runtime_data

    entities: list[DioChaconCover] = []
    for device in dio_chacon_data.list_devices:
        if device["type"] == DeviceTypeEnum.SHUTTER.value:
            cover = DioChaconCover(dio_chacon_data.dio_chacon_client, device)
            # Registers a callback to update the device state when the server sends an event
            dio_chacon_data.dio_chacon_client.set_callback_device_state_by_device(
                cover.target_id, cover.callback_device_state
            )
            entities.append(cover)

    async_add_entities(entities)


class DioChaconCover(DioChaconEntity, CoverEntity):
    """Object for controlling a Dio Chacon cover."""

    # To avoid having name twice
    _attr_has_entity_name = False

    _attr_device_class = CoverDeviceClass.SHUTTER

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        dio_chacon_client: DIOChaconAPIClient,
        device: dict[str, Any],
    ) -> None:
        """Initialize the cover."""

        _LOGGER.debug(
            "Adding DIO Chacon SHUTTER Cover with id=%s, name=%s, openlevel=%s, movement=%s and connected=%s",
            device["id"],
            device["name"],
            device["openlevel"],
            device["movement"],
            device["connected"],
        )

        super().__init__(
            dio_chacon_client, device["id"], device["name"], device["model"]
        )

        self._attr_available = device["connected"]
        self._attr_current_cover_position = device["openlevel"]
        self._attr_is_closing = device["movement"] == ShutterMoveEnum.DOWN.value
        self._attr_is_opening = device["movement"] == ShutterMoveEnum.UP.value
        self._attr_is_closed = self._attr_current_cover_position == 0

    # callback coroutine for device state notification pushed from the server
    def callback_device_state(self, data: dict[str, Any]) -> None:
        """Receive callback for device state notification pushed from the server."""

        _LOGGER.debug("Data received from server %s", data)
        self._attr_available = data["connected"]
        self._attr_current_cover_position = data["openlevel"]
        self._attr_is_closing = data["movement"] == ShutterMoveEnum.DOWN.value
        self._attr_is_opening = data["movement"] == ShutterMoveEnum.UP.value
        self._attr_is_closed = self._attr_current_cover_position == 0
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""

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

            await self.dio_chacon_client.move_shutter_direction(
                self.target_id, ShutterMoveEnum.DOWN
            )

        # Closed status is effective after the server callback that triggers async_set_updated_data on the coordinator

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""

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

            await self.dio_chacon_client.move_shutter_direction(
                self.target_id, ShutterMoveEnum.UP
            )

        # Opened status is effective after the server callback that triggers async_set_updated_data on the coordinator

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""

        _LOGGER.debug("Stop cover %s , %s", self.target_id, self._attr_name)

        self._attr_is_opening = False
        self._attr_is_closing = False
        self.async_write_ha_state()

        await self.dio_chacon_client.move_shutter_direction(
            self.target_id, ShutterMoveEnum.STOP
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover open position in percentage."""
        position: int = kwargs[ATTR_POSITION]

        _LOGGER.debug(
            "Set cover position %i, %s , %s", position, self.target_id, self._attr_name
        )

        await self.dio_chacon_client.move_shutter_percentage(self.target_id, position)

        # Movement status (closing or opening) is effective via the server callback that triggers async_set_updated_data on the coordinator
