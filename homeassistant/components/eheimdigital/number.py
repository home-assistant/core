"""EHEIM Digital numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.heater import EheimDigitalHeater
from eheimdigital.types import HeaterUnit

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import (
    PERCENTAGE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EheimDigitalConfigEntry, EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity

PARALLEL_UPDATES = 0

_DeviceT_co = TypeVar("_DeviceT_co", bound=EheimDigitalDevice, covariant=True)


@dataclass(frozen=True, kw_only=True)
class EheimDigitalNumberDescription(NumberEntityDescription, Generic[_DeviceT_co]):
    """Class describing EHEIM Digital sensor entities."""

    value_fn: Callable[[_DeviceT_co], float | None]
    set_value_fn: Callable[[_DeviceT_co, float], Awaitable[None]]
    uom_fn: Callable[[_DeviceT_co], str] | None = None


CLASSICVARIO_DESCRIPTIONS: tuple[
    EheimDigitalNumberDescription[EheimDigitalClassicVario], ...
] = (
    EheimDigitalNumberDescription[EheimDigitalClassicVario](
        key="manual_speed",
        translation_key="manual_speed",
        entity_category=EntityCategory.CONFIG,
        native_step=PRECISION_WHOLE,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.manual_speed,
        set_value_fn=lambda device, value: device.set_manual_speed(int(value)),
    ),
    EheimDigitalNumberDescription[EheimDigitalClassicVario](
        key="day_speed",
        translation_key="day_speed",
        entity_category=EntityCategory.CONFIG,
        native_step=PRECISION_WHOLE,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.day_speed,
        set_value_fn=lambda device, value: device.set_day_speed(int(value)),
    ),
    EheimDigitalNumberDescription[EheimDigitalClassicVario](
        key="night_speed",
        translation_key="night_speed",
        entity_category=EntityCategory.CONFIG,
        native_step=PRECISION_WHOLE,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device: device.night_speed,
        set_value_fn=lambda device, value: device.set_night_speed(int(value)),
    ),
)

HEATER_DESCRIPTIONS: tuple[EheimDigitalNumberDescription[EheimDigitalHeater], ...] = (
    EheimDigitalNumberDescription[EheimDigitalHeater](
        key="temperature_offset",
        translation_key="temperature_offset",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-3,
        native_max_value=3,
        native_step=PRECISION_TENTHS,
        device_class=NumberDeviceClass.TEMPERATURE,
        uom_fn=lambda device: (
            UnitOfTemperature.CELSIUS
            if device.temperature_unit is HeaterUnit.CELSIUS
            else UnitOfTemperature.FAHRENHEIT
        ),
        value_fn=lambda device: device.temperature_offset,
        set_value_fn=lambda device, value: device.set_temperature_offset(value),
    ),
    EheimDigitalNumberDescription[EheimDigitalHeater](
        key="night_temperature_offset",
        translation_key="night_temperature_offset",
        entity_category=EntityCategory.CONFIG,
        native_min_value=-5,
        native_max_value=5,
        native_step=PRECISION_HALVES,
        device_class=NumberDeviceClass.TEMPERATURE,
        uom_fn=lambda device: (
            UnitOfTemperature.CELSIUS
            if device.temperature_unit is HeaterUnit.CELSIUS
            else UnitOfTemperature.FAHRENHEIT
        ),
        value_fn=lambda device: device.night_temperature_offset,
        set_value_fn=lambda device, value: device.set_night_temperature_offset(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the callbacks for the coordinator so numbers can be added as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_address: dict[str, EheimDigitalDevice],
    ) -> None:
        """Set up the number entities for one or multiple devices."""
        entities: list[EheimDigitalNumber[EheimDigitalDevice]] = []
        for device in device_address.values():
            if isinstance(device, EheimDigitalClassicVario):
                entities.extend(
                    EheimDigitalNumber[EheimDigitalClassicVario](
                        coordinator, device, description
                    )
                    for description in CLASSICVARIO_DESCRIPTIONS
                )
            if isinstance(device, EheimDigitalHeater):
                entities.extend(
                    EheimDigitalNumber[EheimDigitalHeater](
                        coordinator, device, description
                    )
                    for description in HEATER_DESCRIPTIONS
                )

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)
    async_setup_device_entities(coordinator.hub.devices)


class EheimDigitalNumber(
    EheimDigitalEntity[_DeviceT_co], NumberEntity, Generic[_DeviceT_co]
):
    """Represent a EHEIM Digital number entity."""

    entity_description: EheimDigitalNumberDescription[_DeviceT_co]

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: _DeviceT_co,
        description: EheimDigitalNumberDescription[_DeviceT_co],
    ) -> None:
        """Initialize an EHEIM Digital number entity."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_address}_{description.key}"

    @override
    async def async_set_native_value(self, value: float) -> None:
        return await self.entity_description.set_value_fn(self._device, value)

    @override
    def _async_update_attrs(self) -> None:
        self._attr_native_value = self.entity_description.value_fn(self._device)
        self._attr_native_unit_of_measurement = (
            self.entity_description.uom_fn(self._device)
            if self.entity_description.uom_fn
            else self.entity_description.native_unit_of_measurement
        )
