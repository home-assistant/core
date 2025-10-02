"""Support for LetPot number entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from letpot.deviceclient import LetPotDeviceClient
from letpot.models import DeviceFeature

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PRECISION_WHOLE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LetPotConfigEntry, LetPotDeviceCoordinator
from .entity import LetPotEntity, LetPotEntityDescription, exception_handler

# Each change pushes a 'full' device status with the change. The library will cache
# pending changes to avoid overwriting, but try to avoid a lot of parallelism.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LetPotNumberEntityDescription(LetPotEntityDescription, NumberEntityDescription):
    """Describes a LetPot number entity."""

    max_value_fn: Callable[[LetPotDeviceCoordinator], float]
    value_fn: Callable[[LetPotDeviceCoordinator], float | None]
    set_value_fn: Callable[[LetPotDeviceClient, str, float], Coroutine[Any, Any, None]]


NUMBERS: tuple[LetPotNumberEntityDescription, ...] = (
    LetPotNumberEntityDescription(
        key="light_brightness_levels",
        translation_key="light_brightness",
        value_fn=(
            lambda coordinator: coordinator.device_client.get_light_brightness_levels(
                coordinator.device.serial_number
            ).index(coordinator.data.light_brightness)
            + 1
            if coordinator.data.light_brightness is not None
            else None
        ),
        set_value_fn=(
            lambda device_client, serial, value: device_client.set_light_brightness(
                serial,
                device_client.get_light_brightness_levels(serial)[int(value) - 1],
            )
        ),
        supported_fn=(
            lambda coordinator: DeviceFeature.LIGHT_BRIGHTNESS_LEVELS
            in coordinator.device_client.device_info(
                coordinator.device.serial_number
            ).features
        ),
        native_min_value=float(1),
        max_value_fn=lambda coordinator: float(
            len(
                coordinator.device_client.get_light_brightness_levels(
                    coordinator.device.serial_number
                )
            )
        ),
        native_step=PRECISION_WHOLE,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    LetPotNumberEntityDescription(
        key="plant_days",
        translation_key="plant_days",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda coordinator: coordinator.data.plant_days,
        set_value_fn=(
            lambda device_client, serial, value: device_client.set_plant_days(
                serial, int(value)
            )
        ),
        native_min_value=float(0),
        max_value_fn=lambda _: float(999),
        native_step=PRECISION_WHOLE,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LetPotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LetPot number entities based on a config entry and device status/features."""
    coordinators = entry.runtime_data
    async_add_entities(
        LetPotNumberEntity(coordinator, description)
        for description in NUMBERS
        for coordinator in coordinators
        if description.supported_fn(coordinator)
    )


class LetPotNumberEntity(LetPotEntity, NumberEntity):
    """Defines a LetPot number entity."""

    entity_description: LetPotNumberEntityDescription

    def __init__(
        self,
        coordinator: LetPotDeviceCoordinator,
        description: LetPotNumberEntityDescription,
    ) -> None:
        """Initialize LetPot number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{coordinator.device.serial_number}_{description.key}"

    @property
    def native_max_value(self) -> float:
        """Return the maximum available value."""
        return self.entity_description.max_value_fn(self.coordinator)

    @property
    def native_value(self) -> float | None:
        """Return the number value."""
        return self.entity_description.value_fn(self.coordinator)

    @exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Change the number value."""
        return await self.entity_description.set_value_fn(
            self.coordinator.device_client,
            self.coordinator.device.serial_number,
            value,
        )
