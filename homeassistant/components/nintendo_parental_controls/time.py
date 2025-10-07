"""Time platform for Nintendo parental controls."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from enum import StrEnum
import logging
from typing import Any

from pynintendoparental.exceptions import BedtimeOutOfRangeError

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BEDTIME_ALARM_DISABLE, BEDTIME_ALARM_MAX, BEDTIME_ALARM_MIN, DOMAIN
from .coordinator import NintendoParentalControlsConfigEntry, NintendoUpdateCoordinator
from .entity import Device, NintendoDevice

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class NintendoParentalTime(StrEnum):
    """Store keys for Nintendo Parental time."""

    BEDTIME_ALARM = "bedtime_alarm"


@dataclass(kw_only=True, frozen=True)
class NintendoParentalTimeEntityDescription(TimeEntityDescription):
    """Description for Nintendo Parental time entities."""

    value_fn: Callable[[Device], time | None]
    set_value_fn: Callable[[Device, time], Coroutine[Any, Any, None]]


TIME_DESCRIPTIONS: tuple[NintendoParentalTimeEntityDescription, ...] = (
    NintendoParentalTimeEntityDescription(
        key=NintendoParentalTime.BEDTIME_ALARM,
        translation_key=NintendoParentalTime.BEDTIME_ALARM,
        value_fn=lambda device: device.bedtime_alarm,
        set_value_fn=lambda device, value: device.set_bedtime_alarm(value=value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NintendoParentalControlsConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the time platform."""
    async_add_devices(
        NintendoParentalTimeEntity(entry.runtime_data, device, entity)
        for device in entry.runtime_data.api.devices.values()
        for entity in TIME_DESCRIPTIONS
    )


class NintendoParentalTimeEntity(NintendoDevice, TimeEntity):
    """Represent a single time entity."""

    entity_description: NintendoParentalTimeEntityDescription

    def __init__(
        self,
        coordinator: NintendoUpdateCoordinator,
        device: Device,
        description: NintendoParentalTimeEntityDescription,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator=coordinator, device=device, key=description.key)
        self.entity_description = description

    @property
    def native_value(self) -> time | None:
        """Return the time."""
        return self.entity_description.value_fn(self._device)

    async def async_set_value(self, value: time) -> None:
        """Update the value."""
        try:
            await self.entity_description.set_value_fn(self._device, value)
        except BedtimeOutOfRangeError as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="bedtime_alarm_out_of_range",
                translation_placeholders={
                    "value": value.strftime("%H:%M"),
                    "bedtime_alarm_max": BEDTIME_ALARM_MAX,
                    "bedtime_alarm_min": BEDTIME_ALARM_MIN,
                    "bedtime_alarm_disable": BEDTIME_ALARM_DISABLE,
                },
            ) from exc
