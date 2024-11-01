"""TOLO Sauna number controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tololib import (
    FAN_TIMER_MAX,
    POWER_TIMER_MAX,
    SALT_BATH_TIMER_MAX,
    ToloClient,
    ToloSettings,
)

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ToloSaunaUpdateCoordinator
from .entity import ToloSaunaCoordinatorEntity


@dataclass(frozen=True, kw_only=True)
class ToloNumberEntityDescription(NumberEntityDescription):
    """Class describing TOLO Number entities."""

    getter: Callable[[ToloSettings], int | None]
    setter: Callable[[ToloClient, int | None], Any]

    entity_category = EntityCategory.CONFIG
    native_min_value = 0
    native_step = 1


NUMBERS = (
    ToloNumberEntityDescription(
        key="power_timer",
        translation_key="power_timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_max_value=POWER_TIMER_MAX,
        getter=lambda settings: settings.power_timer,
        setter=lambda client, value: client.set_power_timer(value),
    ),
    ToloNumberEntityDescription(
        key="salt_bath_timer",
        translation_key="salt_bath_timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_max_value=SALT_BATH_TIMER_MAX,
        getter=lambda settings: settings.salt_bath_timer,
        setter=lambda client, value: client.set_salt_bath_timer(value),
    ),
    ToloNumberEntityDescription(
        key="fan_timer",
        translation_key="fan_timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_max_value=FAN_TIMER_MAX,
        getter=lambda settings: settings.fan_timer,
        setter=lambda client, value: client.set_fan_timer(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number controls for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ToloNumberEntity(coordinator, entry, description) for description in NUMBERS
    )


class ToloNumberEntity(ToloSaunaCoordinatorEntity, NumberEntity):
    """TOLO Number entity."""

    entity_description: ToloNumberEntityDescription

    def __init__(
        self,
        coordinator: ToloSaunaUpdateCoordinator,
        entry: ConfigEntry,
        entity_description: ToloNumberEntityDescription,
    ) -> None:
        """Initialize TOLO Number entity."""
        super().__init__(coordinator, entry)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"

    @property
    def native_value(self) -> float:
        """Return the value of this TOLO Number entity."""
        return self.entity_description.getter(self.coordinator.data.settings) or 0

    def set_native_value(self, value: float) -> None:
        """Set the value of this TOLO Number entity."""
        int_value = int(value)
        if int_value == 0:
            self.entity_description.setter(self.coordinator.client, None)
            return
        self.entity_description.setter(self.coordinator.client, int_value)
