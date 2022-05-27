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
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN, LOGGER
from .coordinator import IntellifireDataUpdateCoordinator
from .entity import IntellifireEntity


@dataclass
class IntellifireFanRequiredKeysMixin:
    """REquired keys for fan entity."""

    set_fn: Callable[[IntellifireControlAsync, int], Awaitable]
    value_fn: Callable[[IntellifirePollData], bool]
    data_field: str
    named_speeds: list[str]


@dataclass
class IntellifireFanEntityDescription(
    FanEntityDescription, IntellifireFanRequiredKeysMixin
):
    """Describes a fan entity."""


INTELLIFIRE_FANS: tuple[IntellifireFanEntityDescription, ...] = (
    IntellifireFanEntityDescription(
        key="fan",
        name="Fan",
        set_fn=lambda control_api, speed: control_api.set_fan_speed(
            fireplace=control_api.default_fireplace, speed=speed
        ),
        value_fn=lambda data: data.fanspeed,
        data_field="fanspeed",
        named_speeds=[
            "quiet",
            "low",
            "medium",
            "high",
        ],  # off is not included
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fans."""
    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.read_api.data.has_fan:
        async_add_entities(
            IntellifireFan(coordinator=coordinator, description=description)
            for description in INTELLIFIRE_FANS
        )


class IntellifireFan(IntellifireEntity, FanEntity):
    """This is Fan entity for the fireplace."""

    entity_description: IntellifireFanEntityDescription

    @property
    def is_on(self):
        """Return on or off."""
        return self.entity_description.value_fn(self.coordinator.read_api.data) >= 1

    @property
    def percentage(self) -> int | None:
        """Return fan percentage."""
        percent_step = ordered_list_item_to_percentage(
            self.entity_description.named_speeds,
            self.entity_description.named_speeds[0],
        )
        return (
            self.entity_description.value_fn(self.coordinator.read_api.data)
            * percent_step
        )

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE

    @property
    def speed_count(self) -> int:
        """Count of supported speeds."""
        return len(self.entity_description.named_speeds)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        # Get a percent from the preset

        percent = ordered_list_item_to_percentage(
            self.entity_description.named_speeds, preset_mode
        )
        await self.async_set_percentage(percent)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        # Calculate percentage steps
        LOGGER.info("--Setting Fan Speed %s", percentage)
        percent_step = 100.0 / len(self.entity_description.named_speeds)
        int_value = int(math.ceil(float(percentage) / percent_step))
        await self.entity_description.set_fn(self.coordinator.control_api, int_value)
        setattr(
            self.coordinator.read_api, self.entity_description.data_field, int_value
        )
        self.async_write_ha_state()
        LOGGER.info(
            "Fan speed %s [%s%%] = %s: [%s]",
            int_value,
            int_value * 25,
            self.entity_description.name,
            percentage_to_ordered_list_item(
                self.entity_description.named_speeds, int(int_value * percent_step)
            ),
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        LOGGER.debug("%s,%s", percentage, preset_mode)
        LOGGER.debug("On  [ Set Function   ] - Turn On Fan")
        await self.entity_description.set_fn(self.coordinator.control_api, 1)
        await self.async_update_ha_state(force_refresh=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        LOGGER.debug("Off [ Set Function   ] - Turn Off Fan")
        await self.entity_description.set_fn(self.coordinator.control_api, 0)
        await self.async_update_ha_state(force_refresh=True)

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable entity if configured with a thermostat."""
        enabled = bool(self.coordinator.data.has_fan)

        if not enabled:
            LOGGER.info(
                "Disabling Fan - IntelliFire device does not appear to have one"
            )
        return enabled
