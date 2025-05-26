"""EHEIM Digital sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.types import FilterErrorCode

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EheimDigitalConfigEntry, EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

_DeviceT_co = TypeVar("_DeviceT_co", bound=EheimDigitalDevice, covariant=True)


@dataclass(frozen=True, kw_only=True)
class EheimDigitalSensorDescription(SensorEntityDescription, Generic[_DeviceT_co]):
    """Class describing EHEIM Digital sensor entities."""

    value_fn: Callable[[_DeviceT_co], float | str | None]


CLASSICVARIO_DESCRIPTIONS: tuple[
    EheimDigitalSensorDescription[EheimDigitalClassicVario], ...
] = (
    EheimDigitalSensorDescription[EheimDigitalClassicVario](
        key="current_speed",
        translation_key="current_speed",
        value_fn=lambda device: device.current_speed,
        native_unit_of_measurement=PERCENTAGE,
    ),
    EheimDigitalSensorDescription[EheimDigitalClassicVario](
        key="service_hours",
        translation_key="service_hours",
        value_fn=lambda device: device.service_hours,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EheimDigitalSensorDescription[EheimDigitalClassicVario](
        key="error_code",
        translation_key="error_code",
        value_fn=(
            lambda device: device.error_code.name.lower()
            if device.error_code is not None
            else None
        ),
        device_class=SensorDeviceClass.ENUM,
        options=[name.lower() for name in FilterErrorCode._member_names_],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the callbacks for the coordinator so lights can be added as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_address: dict[str, EheimDigitalDevice],
    ) -> None:
        """Set up the light entities for one or multiple devices."""
        entities: list[EheimDigitalSensor[EheimDigitalDevice]] = []
        for device in device_address.values():
            if isinstance(device, EheimDigitalClassicVario):
                entities += [
                    EheimDigitalSensor[EheimDigitalClassicVario](
                        coordinator, device, description
                    )
                    for description in CLASSICVARIO_DESCRIPTIONS
                ]

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)
    async_setup_device_entities(coordinator.hub.devices)


class EheimDigitalSensor(
    EheimDigitalEntity[_DeviceT_co], SensorEntity, Generic[_DeviceT_co]
):
    """Represent a EHEIM Digital sensor entity."""

    entity_description: EheimDigitalSensorDescription[_DeviceT_co]

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: _DeviceT_co,
        description: EheimDigitalSensorDescription[_DeviceT_co],
    ) -> None:
        """Initialize an EHEIM Digital number entity."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_address}_{description.key}"

    @override
    def _async_update_attrs(self) -> None:
        self._attr_native_value = self.entity_description.value_fn(self._device)
