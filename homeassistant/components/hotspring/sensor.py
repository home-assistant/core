"""Support for Hot Spring sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from hotspring import Spa

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import HotSpringConfigEntry, HotSpringDataUpdateCoordinator
from .entity import HotSpringEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HotSpringSensorEntityDescription(SensorEntityDescription):
    """Describes Hot Spring sensor entity."""

    exists_fn: Callable[[Spa], bool] = lambda _: True
    value_fn: Callable[[Spa], StateType]


SENSORS: tuple[HotSpringSensorEntityDescription, ...] = (
    HotSpringSensorEntityDescription(
        key="current_temperature",
        translation_key="current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda spa: spa.heater.current_temperature,
    ),
    HotSpringSensorEntityDescription(
        key="water_care_120_day_timer",
        translation_key="water_care_120_day_timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda spa: spa.water_care.one_twenty_day_timer,
        exists_fn=lambda spa: spa.water_care.cartridge_installed,
    ),
    HotSpringSensorEntityDescription(
        key="water_care_salt_value",
        translation_key="water_care_salt_value",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda spa: spa.water_care.salt_value,
        exists_fn=lambda spa: spa.water_care.cartridge_installed,
    ),
    HotSpringSensorEntityDescription(
        key="water_care_10_day_timer",
        translation_key="water_care_10_day_timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda spa: spa.water_care.ten_day_timer,
        exists_fn=lambda spa: spa.water_care.cartridge_installed,
    ),
    HotSpringSensorEntityDescription(
        key="control_box_version",
        translation_key="control_box_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda spa: spa.versions.control_box,
        exists_fn=lambda spa: bool(spa.versions.control_box),
    ),
    HotSpringSensorEntityDescription(
        key="wifi_dongle_version",
        translation_key="wifi_dongle_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda spa: spa.versions.wifi_dongle,
        exists_fn=lambda spa: bool(spa.versions.wifi_dongle),
    ),
    HotSpringSensorEntityDescription(
        key="fwss_version",
        translation_key="fwss_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda spa: spa.versions.fwss,
        exists_fn=lambda spa: bool(spa.versions.fwss),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HotSpringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hot Spring sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        HotSpringSensorEntity(coordinator, description)
        for description in SENSORS
        if description.exists_fn(coordinator.data)
    )


class HotSpringSensorEntity(HotSpringEntity, SensorEntity):
    """Defines a Hot Spring sensor entity."""

    entity_description: HotSpringSensorEntityDescription

    def __init__(
        self,
        coordinator: HotSpringDataUpdateCoordinator,
        description: HotSpringSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
