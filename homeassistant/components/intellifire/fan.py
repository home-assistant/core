"""Fan definition for Intellifire."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import math
from typing import Any

from intellifire4py import IntellifireControlAsync, IntellifirePollData

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN, LOGGER
from .coordinator import IntellifireDataUpdateCoordinator
from .entity import IntellifireEntity


@dataclass
class IntellifireFanRequiredKeysMixin:
    """Required keys for fan entity."""

    set_fn: Callable[[IntellifireControlAsync, int], Awaitable]
    value_fn: Callable[[IntellifirePollData], bool]
    speed_range: tuple[int, int]


@dataclass
class IntellifireFanEntityDescription(
    FanEntityDescription, IntellifireFanRequiredKeysMixin
):
    """Describes a fan entity."""


INTELLIFIRE_FANS: tuple[IntellifireFanEntityDescription, ...] = (
    IntellifireFanEntityDescription(
        key="fan",
        translation_key="fan",
        set_fn=lambda control_api, speed: control_api.set_fan_speed(speed=speed),
        value_fn=lambda data: data.fanspeed,
        speed_range=(1, 4),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fans."""
    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.data.has_fan:
        async_add_entities(
            IntellifireFan(coordinator=coordinator, description=description)
            for description in INTELLIFIRE_FANS
        )
        return
    LOGGER.debug("Disabling Fan - IntelliFire device does not appear to have one")


class IntellifireFan(IntellifireEntity, FanEntity):
    """Fan entity for the fireplace."""

    entity_description: IntellifireFanEntityDescription
    _attr_supported_features = FanEntityFeature.SET_SPEED

    @property
    def is_on(self) -> bool:
        """Return on or off."""
        return self.entity_description.value_fn(self.coordinator.read_api.data) >= 1

    @property
    def percentage(self) -> int | None:
        """Return fan percentage."""
        return ranged_value_to_percentage(
            self.entity_description.speed_range, self.coordinator.read_api.data.fanspeed
        )

    @property
    def speed_count(self) -> int:
        """Count of supported speeds."""
        return self.entity_description.speed_range[1]

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        # Calculate percentage steps
        LOGGER.debug("Setting Fan Speed %s", percentage)

        int_value = math.ceil(
            percentage_to_ranged_value(self.entity_description.speed_range, percentage)
        )
        await self.entity_description.set_fn(self.coordinator.control_api, int_value)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage:
            int_value = math.ceil(
                percentage_to_ranged_value(
                    self.entity_description.speed_range, percentage
                )
            )
        else:
            int_value = 1
        await self.entity_description.set_fn(self.coordinator.control_api, int_value)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.entity_description.set_fn(self.coordinator.control_api, 0)
        await self.coordinator.async_request_refresh()
