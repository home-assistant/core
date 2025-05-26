"""EHEIM Digital time entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import time
from typing import Generic, TypeVar, final, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.heater import EheimDigitalHeater

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EheimDigitalConfigEntry, EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity

PARALLEL_UPDATES = 0

_DeviceT_co = TypeVar("_DeviceT_co", bound=EheimDigitalDevice, covariant=True)


@dataclass(frozen=True, kw_only=True)
class EheimDigitalTimeDescription(TimeEntityDescription, Generic[_DeviceT_co]):
    """Class describing EHEIM Digital time entities."""

    value_fn: Callable[[_DeviceT_co], time | None]
    set_value_fn: Callable[[_DeviceT_co, time], Awaitable[None]]


CLASSICVARIO_DESCRIPTIONS: tuple[
    EheimDigitalTimeDescription[EheimDigitalClassicVario], ...
] = (
    EheimDigitalTimeDescription[EheimDigitalClassicVario](
        key="day_start_time",
        translation_key="day_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.day_start_time,
        set_value_fn=lambda device, value: device.set_day_start_time(value),
    ),
    EheimDigitalTimeDescription[EheimDigitalClassicVario](
        key="night_start_time",
        translation_key="night_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.night_start_time,
        set_value_fn=lambda device, value: device.set_night_start_time(value),
    ),
)

HEATER_DESCRIPTIONS: tuple[EheimDigitalTimeDescription[EheimDigitalHeater], ...] = (
    EheimDigitalTimeDescription[EheimDigitalHeater](
        key="day_start_time",
        translation_key="day_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.day_start_time,
        set_value_fn=lambda device, value: device.set_day_start_time(value),
    ),
    EheimDigitalTimeDescription[EheimDigitalHeater](
        key="night_start_time",
        translation_key="night_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.night_start_time,
        set_value_fn=lambda device, value: device.set_night_start_time(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the callbacks for the coordinator so times can be added as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_address: dict[str, EheimDigitalDevice],
    ) -> None:
        """Set up the time entities for one or multiple devices."""
        entities: list[EheimDigitalTime[EheimDigitalDevice]] = []
        for device in device_address.values():
            if isinstance(device, EheimDigitalClassicVario):
                entities.extend(
                    EheimDigitalTime[EheimDigitalClassicVario](
                        coordinator, device, description
                    )
                    for description in CLASSICVARIO_DESCRIPTIONS
                )
            if isinstance(device, EheimDigitalHeater):
                entities.extend(
                    EheimDigitalTime[EheimDigitalHeater](
                        coordinator, device, description
                    )
                    for description in HEATER_DESCRIPTIONS
                )

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)
    async_setup_device_entities(coordinator.hub.devices)


@final
class EheimDigitalTime(
    EheimDigitalEntity[_DeviceT_co], TimeEntity, Generic[_DeviceT_co]
):
    """Represent an EHEIM Digital time entity."""

    entity_description: EheimDigitalTimeDescription[_DeviceT_co]

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: _DeviceT_co,
        description: EheimDigitalTimeDescription[_DeviceT_co],
    ) -> None:
        """Initialize an EHEIM Digital time entity."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.mac_address}_{description.key}"

    @override
    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        return await self.entity_description.set_value_fn(self._device, value)

    @override
    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        self._attr_native_value = self.entity_description.value_fn(self._device)
