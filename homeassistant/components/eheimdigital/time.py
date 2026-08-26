"""EHEIM Digital time entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import time
from typing import Any, final, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.filter import EheimDigitalFilter
from eheimdigital.heater import EheimDigitalHeater
from eheimdigital.reeflex import EheimDigitalReeflexUV

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EheimDigitalConfigEntry, EheimDigitalDeviceUpdateCoordinator
from .entity import EheimDigitalEntity, exception_handler

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EheimDigitalTimeDescription[_DeviceT: EheimDigitalDevice](TimeEntityDescription):
    """Class describing EHEIM Digital time entities."""

    value_fn: Callable[[_DeviceT], time | None]
    set_value_fn: Callable[[_DeviceT, time], Awaitable[None]]


REEFLEX_DESCRIPTIONS: tuple[EheimDigitalTimeDescription[EheimDigitalReeflexUV], ...] = (
    EheimDigitalTimeDescription[EheimDigitalReeflexUV](
        key="start_time",
        translation_key="start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.start_time,
        set_value_fn=lambda device, value: device.set_day_start_time(value),
    ),
)

FILTER_DESCRIPTIONS: tuple[EheimDigitalTimeDescription[EheimDigitalFilter], ...] = (
    EheimDigitalTimeDescription[EheimDigitalFilter](
        key="day_start_time",
        translation_key="day_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.day_start_time,
        set_value_fn=lambda device, value: device.set_day_start_time(value),
    ),
    EheimDigitalTimeDescription[EheimDigitalFilter](
        key="night_start_time",
        translation_key="night_start_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: device.night_start_time,
        set_value_fn=lambda device, value: device.set_night_start_time(value),
    ),
)

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
    """Set up callbacks for the coordinator to add times as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_coordinator: EheimDigitalDeviceUpdateCoordinator[Any],
    ) -> None:
        """Set up the time entities for one or multiple devices."""
        entities: list[EheimDigitalTime[Any]] = []
        if isinstance(device_coordinator.data, EheimDigitalFilter):
            entities.extend(
                EheimDigitalTime[EheimDigitalFilter](device_coordinator, description)
                for description in FILTER_DESCRIPTIONS
                if description.key
                in device_coordinator.data.packet_mapping[device_coordinator.msg_title]
            )
        if isinstance(device_coordinator.data, EheimDigitalClassicVario):
            entities.extend(
                EheimDigitalTime[EheimDigitalClassicVario](
                    device_coordinator, description
                )
                for description in CLASSICVARIO_DESCRIPTIONS
                if description.key
                in device_coordinator.data.packet_mapping[device_coordinator.msg_title]
            )
        if isinstance(device_coordinator.data, EheimDigitalHeater):
            entities.extend(
                EheimDigitalTime[EheimDigitalHeater](device_coordinator, description)
                for description in HEATER_DESCRIPTIONS
                if description.key
                in device_coordinator.data.packet_mapping[device_coordinator.msg_title]
            )
        if isinstance(device_coordinator.data, EheimDigitalReeflexUV):
            entities.extend(
                EheimDigitalTime[EheimDigitalReeflexUV](device_coordinator, description)
                for description in REEFLEX_DESCRIPTIONS
                if description.key
                in device_coordinator.data.packet_mapping[device_coordinator.msg_title]
            )

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)


@final
class EheimDigitalTime[_DeviceT: EheimDigitalDevice](
    EheimDigitalEntity[_DeviceT], TimeEntity
):
    """Represent an EHEIM Digital time entity."""

    entity_description: EheimDigitalTimeDescription[_DeviceT]

    def __init__(
        self,
        coordinator: EheimDigitalDeviceUpdateCoordinator[_DeviceT],
        description: EheimDigitalTimeDescription[_DeviceT],
    ) -> None:
        """Initialize an EHEIM Digital time entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_address}_{description.key}"

    @override
    @exception_handler
    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        return await self.entity_description.set_value_fn(self._device, value)

    @override
    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        self._attr_native_value = self.entity_description.value_fn(self._device)
