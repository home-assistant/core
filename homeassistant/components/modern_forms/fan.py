"""Support for Modern Forms Fan Fans."""

from __future__ import annotations

from typing import Any

from aiomodernforms.const import FAN_POWER_OFF, FAN_POWER_ON
import voluptuous as vol

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from . import modernforms_exception_handler
from .const import (
    ATTR_SLEEP_TIME,
    CLEAR_TIMER,
    DOMAIN,
    OPT_ON,
    OPT_SPEED,
    SERVICE_CLEAR_FAN_SLEEP_TIMER,
    SERVICE_SET_FAN_SLEEP_TIMER,
)
from .coordinator import ModernFormsDataUpdateCoordinator
from .entity import ModernFormsDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Modern Forms platform from config entry."""

    coordinator: ModernFormsDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_FAN_SLEEP_TIMER,
        {
            vol.Required(ATTR_SLEEP_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=1440)
            ),
        },
        "async_set_fan_sleep_timer",
    )

    platform.async_register_entity_service(
        SERVICE_CLEAR_FAN_SLEEP_TIMER,
        None,
        "async_clear_fan_sleep_timer",
    )

    async_add_entities(
        [ModernFormsFanEntity(entry_id=config_entry.entry_id, coordinator=coordinator)]
    )


class ModernFormsFanEntity(FanEntity, ModernFormsDeviceEntity):
    """Defines a Modern Forms light."""

    SPEED_RANGE = (1, 6)  # off is not included

    _attr_supported_features = (
        FanEntityFeature.DIRECTION
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_translation_key = "fan"

    def __init__(
        self, entry_id: str, coordinator: ModernFormsDataUpdateCoordinator
    ) -> None:
        """Initialize Modern Forms light."""
        super().__init__(
            entry_id=entry_id,
            coordinator=coordinator,
        )
        self._attr_unique_id = f"{self.coordinator.data.info.mac_address}"

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        percentage = 0
        if bool(self.coordinator.data.state.fan_on):
            percentage = ranged_value_to_percentage(
                self.SPEED_RANGE, self.coordinator.data.state.fan_speed
            )
        return percentage

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        return self.coordinator.data.state.fan_direction

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self.SPEED_RANGE)

    @property
    def is_on(self) -> bool:
        """Return the state of the fan."""
        return bool(self.coordinator.data.state.fan_on)

    @modernforms_exception_handler
    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        await self.coordinator.modern_forms.fan(direction=direction)

    @modernforms_exception_handler
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage > 0:
            await self.async_turn_on(percentage=percentage)
        else:
            await self.async_turn_off()

    @modernforms_exception_handler
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        data = {OPT_ON: FAN_POWER_ON}

        if percentage:
            data[OPT_SPEED] = round(
                percentage_to_ranged_value(self.SPEED_RANGE, percentage)
            )
        await self.coordinator.modern_forms.fan(**data)

    @modernforms_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.coordinator.modern_forms.fan(on=FAN_POWER_OFF)

    @modernforms_exception_handler
    async def async_set_fan_sleep_timer(
        self,
        sleep_time: int,
    ) -> None:
        """Set a Modern Forms light sleep timer."""
        await self.coordinator.modern_forms.fan(sleep=sleep_time * 60)

    @modernforms_exception_handler
    async def async_clear_fan_sleep_timer(
        self,
    ) -> None:
        """Clear a Modern Forms fan sleep timer."""
        await self.coordinator.modern_forms.fan(sleep=CLEAR_TIMER)
