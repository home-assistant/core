"""Comet Blue number integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from eurotronic_cometblue_ha import AsyncCometBlue

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PRECISION_HALVES, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .climate import MAX_TEMP, MIN_TEMP
from .coordinator import CometBlueConfigEntry, CometBlueDataUpdateCoordinator
from .entity import CometBlueBluetoothEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class CometBlueNumberEntityDescription(NumberEntityDescription):
    """Describes a Comet Blue number entity."""

    cometblue_key: str
    set_fn: Callable[[AsyncCometBlue], Any]


DESCRIPTIONS = [
    CometBlueNumberEntityDescription(
        key="offset",
        cometblue_key="tempOffset",
        translation_key="offset",
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        set_fn=lambda x: x.set_temperature_async,
        native_min_value=-5.0,
        native_max_value=5.0,
        native_step=PRECISION_HALVES,
        entity_registry_enabled_default=False,
    ),
    CometBlueNumberEntityDescription(
        key="eco_setpoint",
        cometblue_key="targetTempLow",
        translation_key="eco_setpoint",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        set_fn=lambda x: x.set_temperature_async,
        native_min_value=MIN_TEMP,
        native_max_value=MAX_TEMP,
        native_step=PRECISION_HALVES,
    ),
    CometBlueNumberEntityDescription(
        key="comfort_setpoint",
        cometblue_key="targetTempHigh",
        translation_key="comfort_setpoint",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        set_fn=lambda x: x.set_temperature_async,
        native_min_value=MIN_TEMP,
        native_max_value=MAX_TEMP,
        native_step=PRECISION_HALVES,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CometBlueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the client entities."""

    coordinator = entry.runtime_data
    entities: list[CometBlueNumberEntity] = [
        CometBlueNumberEntity(coordinator, description) for description in DESCRIPTIONS
    ]

    async_add_entities(entities)


class CometBlueNumberEntity(CometBlueBluetoothEntity, NumberEntity):
    """Representation of a number."""

    entity_description: CometBlueNumberEntityDescription

    def __init__(
        self,
        coordinator: CometBlueDataUpdateCoordinator,
        description: CometBlueNumberEntityDescription,
    ) -> None:
        """Initialize CometBlueNumberEntity."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}-{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return self.coordinator.data.temperatures.get(
            self.entity_description.cometblue_key
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update to the device."""

        await self.coordinator.send_command(
            self.entity_description.set_fn(self.coordinator.device),
            {
                "values": {
                    # manual temperature always needs to be set,
                    # otherwise TRV will turn OFF
                    "manualTemp": self.coordinator.data.temperatures["manualTemp"],
                    self.entity_description.cometblue_key: value,
                }
            },
        )
        await self.coordinator.async_request_refresh()
