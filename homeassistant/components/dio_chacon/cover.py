"""Cover Platform for Dio Chacon REV-SHUTTER devices."""

import logging
from typing import Any

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

from .coordinator import DioChaconDataUpdateCoordinator
from .entity import DioChaconEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        DioChaconCover(coordinator, device)
        for device in coordinator.list_devices
        if device["type"] == DeviceTypeEnum.SHUTTER.value
    )


class DioChaconCover(DioChaconEntity, CoverEntity):
    """Object for controlling a Dio Chacon cover."""

    _attr_should_poll = False
    _attr_assumed_state = True
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: DioChaconDataUpdateCoordinator,
        device,
    ) -> None:
        """Initialize the cover."""

        target_id = device["id"]
        name = device["name"]
        openlevel = device["openlevel"]
        movement = device["movement"]
        connected = device["connected"]
        model = device["model"]
        device_class = CoverDeviceClass.SHUTTER

        _LOGGER.info(
            "Adding DIO Chacon SHUTTER Cover with id=%s, name=%s, openlevel=%s, movement=%s and connected=%s",
            target_id,
            name,
            openlevel,
            movement,
            connected,
        )

        super().__init__(coordinator, target_id, name, model, connected)

        self._attr_current_cover_position = openlevel
        self._attr_is_closing = movement == ShutterMoveEnum.DOWN.value
        self._attr_is_opening = movement == ShutterMoveEnum.UP.value
        self._attr_device_class = device_class

        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return The openlevel of the cover un percentage."""
        if self.coordinator_data and self.coordinator_data["openlevel"]:
            self._attr_current_cover_position = self.coordinator_data["openlevel"]
        return self._attr_current_cover_position

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self.current_cover_position == 0

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self.coordinator_data and self.coordinator_data["movement"]:
            self._attr_is_closing = (
                self.coordinator_data["movement"] == ShutterMoveEnum.DOWN.value
            )
        return self._attr_is_closing

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self.coordinator_data and self.coordinator_data["movement"]:
            self._attr_is_opening = (
                self.coordinator_data["movement"] == ShutterMoveEnum.UP.value
            )
        return self._attr_is_opening

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""

        _LOGGER.debug(
            "Close cover %s , %s, %s",
            self._target_id,
            self._attr_name,
            self.is_closed,
        )

        # closes effectively only if cover is not already closing and not fully closed
        if not self._attr_is_closing and not self.is_closed:
            self._attr_is_closing = True
            self.async_write_ha_state()

            await self.dio_chacon_client.move_shutter_direction(
                self._target_id, ShutterMoveEnum.DOWN
            )

        # Closed signal is managed via the callback that triggers async_set_updated_data on the coordinator

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""

        _LOGGER.debug(
            "Open cover %s , %s, %s",
            self._target_id,
            self._attr_name,
            self.current_cover_position,
        )

        # opens effectively only if cover is not already opening and not fully opened
        if not self._attr_is_opening and self.current_cover_position != 100:
            self._attr_is_opening = True
            self.async_write_ha_state()

            await self.dio_chacon_client.move_shutter_direction(
                self._target_id, ShutterMoveEnum.UP
            )

        # Opened signal is managed via the callback that triggers async_set_updated_data on the coordinator

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""

        _LOGGER.debug("Stop cover %s , %s", self._target_id, self._attr_name)

        self._attr_is_opening = False
        self._attr_is_closing = False
        self.async_write_ha_state()

        await self.dio_chacon_client.move_shutter_direction(
            self._target_id, ShutterMoveEnum.STOP
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover open position in percentage."""
        position: int = kwargs[ATTR_POSITION]

        _LOGGER.debug(
            "Set cover position %i, %s , %s", position, self._target_id, self._attr_name
        )

        await self.dio_chacon_client.move_shutter_percentage(self._target_id, position)

        # Movement signal is managed via the callback that triggers async_set_updated_data on the coordinator
