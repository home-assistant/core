"""Number platform for Nintendo Parental controls."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pynintendoparental.exceptions import DailyPlaytimeOutOfRangeError

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DAILY_PLAYTIME_MAX,
    DAILY_PLAYTIME_MIN,
    DAILY_PLAYTIME_UNLIMITED,
    DOMAIN,
)
from .coordinator import NintendoParentalControlsConfigEntry, NintendoUpdateCoordinator
from .entity import Device, NintendoDevice

PARALLEL_UPDATES = 0


class NintendoParentalNumber(StrEnum):
    """Store keys for Nintendo Parental numbers."""

    TODAY_MAX_SCREENTIME = "today_max_screentime"


@dataclass(kw_only=True, frozen=True)
class NintendoParentalControlsNumberEntityDescription(NumberEntityDescription):
    """Description for Nintendo Parental number entities."""

    value_fn: Callable[[Device], int | float | None]
    set_native_value_fn: Callable[[Device, float], Coroutine[Any, Any, None]]


NUMBER_DESCRIPTIONS: tuple[NintendoParentalControlsNumberEntityDescription, ...] = (
    NintendoParentalControlsNumberEntityDescription(
        key=NintendoParentalNumber.TODAY_MAX_SCREENTIME,
        translation_key=NintendoParentalNumber.TODAY_MAX_SCREENTIME,
        native_min_value=-1,
        native_step=1,
        native_max_value=360,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        set_native_value_fn=lambda device, value: device.update_max_daily_playtime(
            minutes=value
        ),
        value_fn=lambda device: device.limit_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NintendoParentalControlsConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number platform."""
    async_add_devices(
        NintendoParentalControlsNumberEntity(entry.runtime_data, device, entity)
        for device in entry.runtime_data.api.devices.values()
        for entity in NUMBER_DESCRIPTIONS
    )


class NintendoParentalControlsNumberEntity(NintendoDevice, NumberEntity):
    """Represent a Nintendo Parental number entity."""

    entity_description: NintendoParentalControlsNumberEntityDescription

    def __init__(
        self,
        coordinator: NintendoUpdateCoordinator,
        device: Device,
        description: NintendoParentalControlsNumberEntityDescription,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator=coordinator, device=device, key=description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        return self.entity_description.value_fn(self._device)

    async def async_set_native_value(self, value: float) -> None:
        """Update entity state."""
        try:
            await self.entity_description.set_native_value_fn(self._device, value)
        except DailyPlaytimeOutOfRangeError as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="daily_playtime_out_of_range",
                translation_placeholders={
                    "value": str(value),
                    "daily_playtime_min": DAILY_PLAYTIME_MIN,
                    "daily_playtime_max": DAILY_PLAYTIME_MAX,
                    "daily_playtime_unlimited": DAILY_PLAYTIME_UNLIMITED,
                },
            ) from exc
