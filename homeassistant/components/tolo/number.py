"""TOLO Sauna number controls."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ToloSaunaCoordinatorEntity, ToloSaunaUpdateCoordinator
from ...const import TIME_MINUTES
from ...helpers.entity import EntityCategory
from .const import DOMAIN, FAN_TIMER_MAX, POWER_TIMER_MAX, SALT_BATH_TIMER_MAX


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number controls for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ToloNumberEntity(coordinator, entry, description)
            for description in (
                ToloNumberEntityDescription(
                    key="power_timer",
                    icon="mdi:power-settings",
                    name="Power Timer",
                    unit_of_measurement=TIME_MINUTES,
                    max_value=POWER_TIMER_MAX,
                    getter=coordinator.data.settings.power_timer,
                    setter=coordinator.client.set_power_timer,
                ),
                ToloNumberEntityDescription(
                    key="salt_bath_timer",
                    icon="mdi:shaker-outline",
                    name="Salt Bath Timer",
                    unit_of_measurement=TIME_MINUTES,
                    max_value=SALT_BATH_TIMER_MAX,
                    getter=coordinator.data.settings.salt_bath_timer,
                    setter=coordinator.client.set_salt_bath_timer,
                ),
                ToloNumberEntityDescription(
                    key="fan_timer",
                    icon="mdi:fan-auto",
                    name="Fan Timer",
                    unit_of_measurement=TIME_MINUTES,
                    max_value=FAN_TIMER_MAX,
                    getter=coordinator.data.settings.fan_timer,
                    setter=coordinator.client.set_fan_timer,
                ),
            )
        ]
    )


@dataclass
class ToloNumberEntityDescriptionBase:
    """Required values when describing TOLO Number entities."""

    getter: Callable[[], int | None]
    setter: Callable[[int | None], None]


@dataclass
class ToloNumberEntityDescription(
    NumberEntityDescription, ToloNumberEntityDescriptionBase
):
    """Class describing TOLO Number entities."""

    entity_category = EntityCategory.CONFIG
    min_value = 0
    step = 1


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
    def value(self) -> float:
        """Return the value of this TOLO Number entity."""
        return self.entity_description.getter() or 0

    def set_value(self, value: float) -> None:
        """Set the value of this TOLO Number entity."""
        int_value = int(value)
        if int_value == 0:
            self.entity_description.setter(None)
            return
        self.entity_description.setter(int_value)
