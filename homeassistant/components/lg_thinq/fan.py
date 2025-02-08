"""Support for fan entities."""

from __future__ import annotations

import logging
from typing import Any

from thinqconnect import DeviceType
from thinqconnect.integration import ExtendedProperty

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity

DEVICE_TYPE_FAN_MAP: dict[DeviceType, tuple[FanEntityDescription, ...]] = {
    DeviceType.CEILING_FAN: (
        FanEntityDescription(
            key=ExtendedProperty.FAN,
            name=None,
        ),
    ),
}

FOUR_STEP_SPEEDS = ["low", "mid", "high", "turbo"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for fan platform."""
    entities: list[ThinQFanEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_FAN_MAP.get(coordinator.api.device.device_type)
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQFanEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(description.key)
                )

    if entities:
        async_add_entities(entities)


class ThinQFanEntity(ThinQEntity, FanEntity):
    """Represent a thinq fan platform."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: FanEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize fan platform."""
        super().__init__(coordinator, entity_description, property_id)

        self._ordered_named_fan_speeds = []
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.TURN_OFF
        )
        if (fan_modes := self.data.fan_modes) is not None:
            self._attr_speed_count = len(fan_modes)
            if self.speed_count == 4:
                self._ordered_named_fan_speeds = FOUR_STEP_SPEEDS

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        # Update power on state.
        self._attr_is_on = self.data.is_on

        # Update fan speed.
        if (
            self.data.is_on
            and (mode := self.data.fan_mode) in self._ordered_named_fan_speeds
        ):
            self._attr_percentage = ordered_list_item_to_percentage(
                self._ordered_named_fan_speeds, mode
            )
        else:
            self._attr_percentage = 0

        _LOGGER.debug(
            "[%s:%s] update status: %s -> %s (percentage=%s)",
            self.coordinator.device_name,
            self.property_id,
            self.data.is_on,
            self.is_on,
            self.percentage,
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return
        try:
            value = percentage_to_ordered_list_item(
                self._ordered_named_fan_speeds, percentage
            )
        except ValueError:
            _LOGGER.exception("Failed to async_set_percentage")
            return

        _LOGGER.debug(
            "[%s:%s] async_set_percentage. percentage=%s, value=%s",
            self.coordinator.device_name,
            self.property_id,
            percentage,
            value,
        )
        await self.async_call_api(
            self.coordinator.api.async_set_fan_mode(self.property_id, value)
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug(
            "[%s:%s] async_turn_on", self.coordinator.device_name, self.property_id
        )
        await self.async_call_api(self.coordinator.api.async_turn_on(self.property_id))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        _LOGGER.debug(
            "[%s:%s] async_turn_off", self.coordinator.device_name, self.property_id
        )
        await self.async_call_api(self.coordinator.api.async_turn_off(self.property_id))
