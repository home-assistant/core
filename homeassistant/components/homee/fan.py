"""The Homee fan platform."""

import math
from typing import Any

from pyHomee.const import AttributeType, NodeProfile
from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from . import HomeeConfigEntry
from .const import DOMAIN
from .entity import HomeeNodeEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Homee fan platform."""

    async_add_devices(
        HomeeFan(node, config_entry)
        for node in config_entry.runtime_data.nodes
        if node.profile == NodeProfile.VENTILATION_CONTROL
    )


class HomeeFan(HomeeNodeEntity, FanEntity):
    """Representation of a Homee fan entity."""

    _attr_translation_key = DOMAIN
    _attr_name = None
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
    _attr_preset_modes = ["manual", "auto", "summer"]
    speed_range = (1, 8)
    _attr_speed_count = int_states_in_range(speed_range)

    def __init__(self, node: HomeeNode, entry: HomeeConfigEntry) -> None:
        """Initialize a Homee fan entity."""
        super().__init__(node, entry)
        self._speed_attribute: HomeeAttribute | None = node.get_attribute_by_type(
            AttributeType.VENTILATION_LEVEL
        )
        self._mode_attribute: HomeeAttribute | None = node.get_attribute_by_type(
            AttributeType.VENTILATION_MODE
        )

    @property
    def supported_features(self) -> FanEntityFeature:
        """Return the supported features based on preset_mode."""
        features = FanEntityFeature.PRESET_MODE

        if self.preset_mode != "auto":
            features |= (
                FanEntityFeature.SET_SPEED
                | FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
            )

        return features

    @property
    def is_on(self) -> bool:
        """Return true if the entity is on."""
        return self.percentage > 0

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        assert self._speed_attribute is not None
        return ranged_value_to_percentage(
            self.speed_range, self._speed_attribute.current_value
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the mode from the float state."""
        assert self._mode_attribute is not None
        return self._attr_preset_modes[int(self._mode_attribute.current_value)]

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        assert self._speed_attribute is not None
        if self._speed_attribute.editable:
            await self.async_set_homee_value(
                self._speed_attribute,
                math.ceil(percentage_to_ranged_value(self.speed_range, percentage)),
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        assert self._mode_attribute is not None
        await self.async_set_homee_value(
            self._mode_attribute, self._attr_preset_modes.index(preset_mode)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        assert self._speed_attribute is not None
        if self._speed_attribute.editable:
            await self.async_set_homee_value(self._speed_attribute, 0)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        else:
            await self.async_set_preset_mode("manual")

        # If no percentage is given, use the last known value.
        assert self._speed_attribute is not None
        if percentage is None:
            percentage = ranged_value_to_percentage(
                self.speed_range,
                self._speed_attribute.last_value,
            )
            # If the last known value is 0, set 100%.
            if percentage == 0:
                percentage = 100

        await self.async_set_percentage(percentage)
