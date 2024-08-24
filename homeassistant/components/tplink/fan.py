"""Support for TPLink Fan devices."""

import logging
import math
from typing import Any

from kasa import Device, Module
from kasa.interfaces import Fan as FanInterface

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up fans."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device
    entities: list[CoordinatedTPLinkEntity] = []
    if Module.Fan in device.modules:
        entities.append(
            TPLinkFanEntity(
                device, parent_coordinator, fan_module=device.modules[Module.Fan]
            )
        )
    entities.extend(
        TPLinkFanEntity(
            child,
            parent_coordinator,
            fan_module=child.modules[Module.Fan],
            parent=device,
        )
        for child in device.children
        if Module.Fan in child.modules
    )
    async_add_entities(entities)


SPEED_RANGE = (1, 4)  # off is not included


class TPLinkFanEntity(CoordinatedTPLinkEntity, FanEntity):
    """Representation of a fan for a TPLink Fan device."""

    _attr_speed_count = int_states_in_range(SPEED_RANGE)
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        fan_module: FanInterface,
        parent: Device | None = None,
    ) -> None:
        """Initialize the fan."""
        self.fan_module = fan_module
        # If _attr_name is None the entity name will be the device name
        self._attr_name = None if parent is None else device.alias

        super().__init__(device, coordinator, parent=parent)

    @async_refresh_after
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is not None:
            value_in_range = math.ceil(
                percentage_to_ranged_value(SPEED_RANGE, percentage)
            )
        else:
            value_in_range = SPEED_RANGE[1]
        await self.fan_module.set_fan_speed_level(value_in_range)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.fan_module.set_fan_speed_level(0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        value_in_range = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self.fan_module.set_fan_speed_level(value_in_range)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        fan_speed = self.fan_module.fan_speed_level
        self._attr_is_on = fan_speed != 0
        if self._attr_is_on:
            self._attr_percentage = ranged_value_to_percentage(SPEED_RANGE, fan_speed)
        else:
            self._attr_percentage = None
