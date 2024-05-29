"""Number platform for Tessie integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tessie_api import set_charge_limit, set_charging_amps, set_speed_limit

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    PRECISION_WHOLE,
    UnitOfElectricCurrent,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TessieConfigEntry
from .coordinator import TessieStateUpdateCoordinator
from .entity import TessieEntity


@dataclass(frozen=True, kw_only=True)
class TessieNumberEntityDescription(NumberEntityDescription):
    """Describes Tessie Number entity."""

    func: Callable
    arg: str
    native_min_value: float
    native_max_value: float
    min_key: str | None = None
    max_key: str


DESCRIPTIONS: tuple[TessieNumberEntityDescription, ...] = (
    TessieNumberEntityDescription(
        key="charge_state_charge_current_request",
        native_step=PRECISION_WHOLE,
        native_min_value=0,
        native_max_value=32,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
        max_key="charge_state_charge_current_request_max",
        func=lambda: set_charging_amps,
        arg="amps",
    ),
    TessieNumberEntityDescription(
        key="charge_state_charge_limit_soc",
        native_step=PRECISION_WHOLE,
        native_min_value=50,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.BATTERY,
        min_key="charge_state_charge_limit_soc_min",
        max_key="charge_state_charge_limit_soc_max",
        func=lambda: set_charge_limit,
        arg="percent",
    ),
    TessieNumberEntityDescription(
        key="vehicle_state_speed_limit_mode_current_limit_mph",
        native_step=PRECISION_WHOLE,
        native_min_value=50,
        native_max_value=120,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=NumberDeviceClass.SPEED,
        mode=NumberMode.BOX,
        min_key="vehicle_state_speed_limit_mode_min_limit_mph",
        max_key="vehicle_state_speed_limit_mode_max_limit_mph",
        func=lambda: set_speed_limit,
        arg="mph",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tessie sensor platform from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        TessieNumberEntity(vehicle, description)
        for vehicle in data.vehicles
        for description in DESCRIPTIONS
        if description.key in vehicle.data
    )


class TessieNumberEntity(TessieEntity, NumberEntity):
    """Number entity for current charge."""

    entity_description: TessieNumberEntityDescription

    def __init__(
        self,
        coordinator: TessieStateUpdateCoordinator,
        description: TessieNumberEntityDescription,
    ) -> None:
        """Initialize the Number entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self._value

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        if self.entity_description.min_key:
            return self.get(
                self.entity_description.min_key,
                self.entity_description.native_min_value,
            )
        return self.entity_description.native_min_value

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self.get(
            self.entity_description.max_key, self.entity_description.native_max_value
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.run(
            self.entity_description.func(), **{self.entity_description.arg: value}
        )
        self.set((self.key, value))
