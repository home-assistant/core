"""Support for Hot Spring sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import math
from typing import override

from hotspring import Spa, TemperatureUnit

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import HotSpringConfigEntry, HotSpringDataUpdateCoordinator
from .entity import HotSpringEntity

PARALLEL_UPDATES = 0


def _fwiq_reading(value: float | None) -> StateType:
    """Map FreshWater IQ sentinels and non-finite readings to unknown.

    ``-1`` is the FreshWater IQ sentinel reported by the device; legitimate
    zero readings and other negative readings are preserved.
    """
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value == -1:
        return None
    return value


@dataclass(frozen=True, kw_only=True)
class HotSpringSensorEntityDescription(SensorEntityDescription):
    """Describes Hot Spring sensor entity."""

    exists_fn: Callable[[Spa], bool] = lambda _: True
    value_fn: Callable[[Spa], StateType]
    unit_fn: Callable[[Spa], str | None] | None = None


FRESHWATER_IQ_SENSORS: tuple[HotSpringSensorEntityDescription, ...] = (
    HotSpringSensorEntityDescription(
        key="freshwater_iq_chlorine",
        translation_key="freshwater_iq_chlorine",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        suggested_display_precision=2,
        value_fn=lambda spa: _fwiq_reading(spa.freshwater_iq.chlorine),
        exists_fn=lambda spa: spa.freshwater_iq.installed,
    ),
    HotSpringSensorEntityDescription(
        key="freshwater_iq_orp",
        translation_key="freshwater_iq_orp",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        suggested_display_precision=0,
        value_fn=lambda spa: _fwiq_reading(spa.freshwater_iq.orp),
        exists_fn=lambda spa: spa.freshwater_iq.installed,
    ),
    HotSpringSensorEntityDescription(
        key="freshwater_iq_ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda spa: _fwiq_reading(spa.freshwater_iq.ph),
        exists_fn=lambda spa: spa.freshwater_iq.installed,
    ),
    HotSpringSensorEntityDescription(
        key="freshwater_iq_sensor_life",
        translation_key="freshwater_iq_sensor_life",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda spa: _fwiq_reading(spa.freshwater_iq.sensor_life_percentage),
        exists_fn=lambda spa: spa.freshwater_iq.installed,
    ),
)

SENSORS: tuple[HotSpringSensorEntityDescription, ...] = (
    HotSpringSensorEntityDescription(
        key="current_temperature",
        translation_key="current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda spa: spa.heater.current_temperature,
        unit_fn=lambda spa: (
            UnitOfTemperature.CELSIUS
            if spa.heater.temperature_unit is TemperatureUnit.CELSIUS
            else UnitOfTemperature.FAHRENHEIT
        ),
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
    *FRESHWATER_IQ_SENSORS,
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

    # The spa may not publish FreshWater IQ data until after setup; add the
    # FreshWater IQ sensors whenever the library first reports it installed.
    added_fwiq_keys: set[str] = set()

    @callback
    def _async_add_freshwater_iq_entities() -> None:
        if not coordinator.data.freshwater_iq.installed:
            return
        new_entities = [
            HotSpringSensorEntity(coordinator, description)
            for description in FRESHWATER_IQ_SENSORS
            if description.key not in added_fwiq_keys
        ]
        added_fwiq_keys.update(entity.entity_description.key for entity in new_entities)
        if new_entities:
            async_add_entities(new_entities)

    if coordinator.data.freshwater_iq.installed:
        return
    entry.async_on_unload(
        coordinator.async_add_listener(_async_add_freshwater_iq_entities)
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
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.coordinator.data)
        return super().native_unit_of_measurement

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
