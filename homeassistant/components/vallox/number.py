"""Support for Vallox ventilation unit numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from vallox_websocket_api import MetricData, Profile, Vallox

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    CONF_NAME,
    EntityCategory,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ValloxConfigEntry, ValloxDataUpdateCoordinator
from .entity import ValloxEntity


class ValloxNumberEntity(ValloxEntity, NumberEntity):
    """Representation of a Vallox number entity."""

    entity_description: ValloxNumberEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxNumberEntityDescription,
    ) -> None:
        """Initialize the Vallox number entity."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the value reported by the unit."""
        return self.entity_description.value_fn(self.coordinator.data)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.entity_description.set_value_fn(self.coordinator.client, value)
        await self.coordinator.async_request_refresh()


@dataclass(frozen=True, kw_only=True)
class ValloxNumberEntityDescription(NumberEntityDescription):
    """Describes Vallox number entity."""

    value_fn: Callable[[MetricData], float | None]
    set_value_fn: Callable[[Vallox, float], Awaitable[None]]


NUMBER_ENTITIES: tuple[ValloxNumberEntityDescription, ...] = (
    ValloxNumberEntityDescription(
        key="supply_air_target_home",
        translation_key="supply_air_target_home",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
        value_fn=lambda data: data.get_temperature_setting(Profile.HOME),
        set_value_fn=lambda client, value: client.set_temperature(Profile.HOME, value),
    ),
    ValloxNumberEntityDescription(
        key="supply_air_target_away",
        translation_key="supply_air_target_away",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
        value_fn=lambda data: data.get_temperature_setting(Profile.AWAY),
        set_value_fn=lambda client, value: client.set_temperature(Profile.AWAY, value),
    ),
    ValloxNumberEntityDescription(
        key="supply_air_target_boost",
        translation_key="supply_air_target_boost",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5.0,
        native_max_value=25.0,
        native_step=1.0,
        value_fn=lambda data: data.get_temperature_setting(Profile.BOOST),
        set_value_fn=lambda client, value: client.set_temperature(Profile.BOOST, value),
    ),
    ValloxNumberEntityDescription(
        key="fan_speed_home",
        translation_key="fan_speed_home",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        native_min_value=1.0,
        native_max_value=100.0,
        native_step=1.0,
        value_fn=lambda data: data.get_fan_speed(Profile.HOME),
        set_value_fn=lambda client, value: client.set_fan_speed(
            Profile.HOME, int(value)
        ),
    ),
    ValloxNumberEntityDescription(
        key="fan_speed_away",
        translation_key="fan_speed_away",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        native_min_value=1.0,
        native_max_value=100.0,
        native_step=1.0,
        value_fn=lambda data: data.get_fan_speed(Profile.AWAY),
        set_value_fn=lambda client, value: client.set_fan_speed(
            Profile.AWAY, int(value)
        ),
    ),
    ValloxNumberEntityDescription(
        key="fan_speed_boost",
        translation_key="fan_speed_boost",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        native_min_value=1.0,
        native_max_value=100.0,
        native_step=1.0,
        value_fn=lambda data: data.get_fan_speed(Profile.BOOST),
        set_value_fn=lambda client, value: client.set_fan_speed(
            Profile.BOOST, int(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValloxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        ValloxNumberEntity(entry.data[CONF_NAME], coordinator, description)
        for description in NUMBER_ENTITIES
    )
