"""Number platform for aerosmart."""

from dataclasses import dataclass
from typing import cast, override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AerosmartConfigEntry
from .entity import AerosmartEntity, AerosmartEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AerosmartNumberEntityDescription(
    NumberEntityDescription, AerosmartEntityDescription
):
    """Describe an aerosmart number entity."""


NUMBER_DESCRIPTIONS: tuple[AerosmartNumberEntityDescription, ...] = (
    AerosmartNumberEntityDescription(
        key="room_temperature_setpoint",
        translation_key="room_temperature_setpoint",
        component="room_temperature",
        attribute="temp_raumluft_soll",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=14.0,
        native_max_value=26.0,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    AerosmartNumberEntityDescription(
        key="domestic_hot_water_temperature_setpoint",
        translation_key="domestic_hot_water_temperature_setpoint",
        component="hot_water_heat_pump",
        attribute="wp_brauchwasser_soll_temp",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=20.0,
        native_max_value=55.0,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AerosmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up aerosmart number entities."""
    runtime = entry.runtime_data
    async_add_entities(
        AerosmartNumberEntity(
            runtime.coordinator_for(description.component), description
        )
        for description in NUMBER_DESCRIPTIONS
    )


class AerosmartNumberEntity(AerosmartEntity, NumberEntity):
    """Represent a writable aerosmart temperature setpoint."""

    entity_description: AerosmartNumberEntityDescription

    @property
    @override
    def native_value(self) -> float | None:
        """Return the confirmed controller value."""
        component = getattr(self.coordinator.device, self.entity_description.component)
        return cast(
            "float | None", getattr(component, self.entity_description.attribute)
        )

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set and confirm the controller value."""
        await self._async_write_verified(value)
