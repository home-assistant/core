"""Support for ESPHome binary sensors."""

from __future__ import annotations

from functools import partial

from aioesphomeapi import BinarySensorInfo, BinarySensorState, EntityInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.util.enum import try_parse_enum

from .entity import EsphomeEntity, platform_async_setup_entry

PARALLEL_UPDATES = 0


class EsphomeBinarySensor(
    EsphomeEntity[BinarySensorInfo, BinarySensorState], BinarySensorEntity
):
    """A binary sensor implementation for ESPHome."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self._static_info.is_status_binary_sensor:
            # Status binary sensors indicated connected state.
            # So in their case what's usually _availability_ is now state
            return self._entry_data.available
        if not self._has_state or self._state.missing_state:
            return None
        return self._state.state

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        self._attr_device_class = try_parse_enum(
            BinarySensorDeviceClass, self._static_info.device_class
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._static_info.is_status_binary_sensor or super().available


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=BinarySensorInfo,
    entity_type=EsphomeBinarySensor,
    state_type=BinarySensorState,
)
