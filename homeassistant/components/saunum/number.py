"""Number platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pysaunum import (
    MAX_DURATION,
    MAX_FAN_DURATION,
    MIN_DURATION,
    MIN_FAN_DURATION,
    SaunumClient,
    SaunumData,
    SaunumException,
)

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry
from .const import DOMAIN
from .entity import LeilSaunaEntity

if TYPE_CHECKING:
    from .coordinator import LeilSaunaCoordinator

PARALLEL_UPDATES = 0

# Default values when device returns None or invalid data
DEFAULT_DURATION_MIN = 120
DEFAULT_FAN_DURATION_MIN = 15


@dataclass(frozen=True, kw_only=True)
class LeilSaunaNumberEntityDescription(NumberEntityDescription):
    """Describes Saunum Leil Sauna number entity."""

    value_fn: Callable[[SaunumData], int | float | None]
    set_value_fn: Callable[[SaunumClient, float], Awaitable[None]]


NUMBERS: tuple[LeilSaunaNumberEntityDescription, ...] = (
    LeilSaunaNumberEntityDescription(
        key="sauna_duration",
        translation_key="sauna_duration",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=1,
        native_max_value=MAX_DURATION,
        native_step=1,
        value_fn=lambda data: (
            duration
            if (duration := data.sauna_duration) is not None and duration > MIN_DURATION
            else DEFAULT_DURATION_MIN
        ),
        set_value_fn=lambda client, value: client.async_set_sauna_duration(int(value)),
    ),
    LeilSaunaNumberEntityDescription(
        key="fan_duration",
        translation_key="fan_duration",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=1,
        native_max_value=MAX_FAN_DURATION,
        native_step=1,
        value_fn=lambda data: (
            fan_dur
            if (fan_dur := data.fan_duration) is not None and fan_dur > MIN_FAN_DURATION
            else DEFAULT_FAN_DURATION_MIN
        ),
        set_value_fn=lambda client, value: client.async_set_fan_duration(int(value)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna number entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        LeilSaunaNumber(coordinator, description) for description in NUMBERS
    )


class LeilSaunaNumber(LeilSaunaEntity, NumberEntity):
    """Representation of a Saunum Leil Sauna number entity."""

    entity_description: LeilSaunaNumberEntityDescription

    def __init__(
        self,
        coordinator: LeilSaunaCoordinator,
        description: LeilSaunaNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        # Prevent changing certain settings when session is active
        session_active = self.coordinator.data.session_active
        if session_active and self.entity_description.key in (
            "sauna_duration",
            "fan_duration",
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"session_active_cannot_change_{self.entity_description.key}",
            )

        try:
            await self.entity_description.set_value_fn(self.coordinator.client, value)
        except SaunumException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=f"set_{self.entity_description.key}_failed",
            ) from err

        await self.coordinator.async_request_refresh()
