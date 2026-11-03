"""Support for Elgato numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from elgato import Elgato

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

from .coordinator import ElgatoConfigEntry, ElgatoData, ElgatoDataUpdateCoordinator
from .entity import ElgatoEntity
from .helpers import color_temperature_range, elgato_device_action

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ElgatoNumberEntityDescription(NumberEntityDescription):
    """Class describing Elgato number entities."""

    has_fn: Callable[[ElgatoData], bool] = lambda _: True
    range_fn: Callable[[ElgatoData], tuple[int, int]] | None = None
    value_fn: Callable[[ElgatoData], float | None]
    set_fn: Callable[[Elgato, float], Awaitable[Any]]


NUMBERS = [
    ElgatoNumberEntityDescription(
        key="power_on_brightness",
        translation_key="power_on_brightness",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        value_fn=lambda x: x.settings.power_on_brightness,
        set_fn=lambda client, value: client.power_on_behavior(brightness=int(value)),
    ),
    ElgatoNumberEntityDescription(
        key="power_on_temperature",
        translation_key="power_on_temperature",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        # Narrows on a device that does color, exactly as the light does.
        range_fn=color_temperature_range,
        native_step=50,
        has_fn=lambda x: x.settings.power_on_temperature is not None,
        # A light set to power on to a color reports a zero, which is not a
        # color temperature. The setting can be changed back, so the entity
        # stays and goes unknown rather than disappearing.
        value_fn=lambda x: (
            color_temperature_mired_to_kelvin(x.settings.power_on_temperature)
            if x.settings.power_on_temperature
            else None
        ),
        set_fn=lambda client, value: client.power_on_behavior(
            temperature=color_temperature_kelvin_to_mired(value)
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElgatoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elgato numbers based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        ElgatoNumberEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in NUMBERS
        if description.has_fn(coordinator.data)
    )


class ElgatoNumberEntity(ElgatoEntity, NumberEntity):
    """Representation of an Elgato number."""

    entity_description: ElgatoNumberEntityDescription

    def __init__(
        self,
        coordinator: ElgatoDataUpdateCoordinator,
        description: ElgatoNumberEntityDescription,
    ) -> None:
        """Initiate Elgato number."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.info.serial_number}_{description.key}"
        )

        if description.range_fn is not None:
            (
                self._attr_native_min_value,
                self._attr_native_max_value,
            ) = description.range_fn(coordinator.data)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the number value."""
        if (value := self.entity_description.value_fn(self.coordinator.data)) is None:
            return None

        # A Kelvin value that survives the trip out does not always survive
        # the trip back. Setting 6500 K stores 153 mireds, which reads as
        # 6535 K, above a maximum that cannot then be set again.
        return min(max(value, self.native_min_value), self.native_max_value)

    @elgato_device_action
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Change the number value."""
        await self.entity_description.set_fn(self.coordinator.client, value)
