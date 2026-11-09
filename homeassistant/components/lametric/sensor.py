"""Support for LaMetric sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from demetriek import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    LaMetricAppsUpdateCoordinator,
    LaMetricConfigEntry,
    LaMetricDataUpdateCoordinator,
)
from .entity import LaMetricAppsEntity, LaMetricEntity
from .helpers import current_widget, widget_options

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LaMetricSensorEntityDescription(SensorEntityDescription):
    """Class describing LaMetric sensor entities."""

    value_fn: Callable[[Device], int | None]


SENSORS = [
    LaMetricSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.wifi.rssi,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMetricConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LaMetric sensor based on a config entry."""
    runtime_data = entry.runtime_data
    async_add_entities(
        [
            *(
                LaMetricSensorEntity(
                    coordinator=runtime_data.device,
                    description=description,
                )
                for description in SENSORS
            ),
            LaMetricAppsSensorEntity(runtime_data.device, runtime_data.apps),
        ]
    )


class LaMetricSensorEntity(LaMetricEntity, SensorEntity):
    """Representation of a LaMetric sensor."""

    entity_description: LaMetricSensorEntityDescription

    def __init__(
        self,
        coordinator: LaMetricDataUpdateCoordinator,
        description: LaMetricSensorEntityDescription,
    ) -> None:
        """Initiate LaMetric sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}-{description.key}"

    @property
    @override
    def native_value(self) -> int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


class LaMetricAppsSensorEntity(LaMetricAppsEntity, SensorEntity):
    """Representation of the widget currently shown on a LaMetric device."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "current_app"

    def __init__(
        self,
        device_coordinator: LaMetricDataUpdateCoordinator,
        apps_coordinator: LaMetricAppsUpdateCoordinator,
    ) -> None:
        """Initialize the LaMetric apps sensor."""
        super().__init__(device_coordinator, apps_coordinator)
        self._attr_unique_id = f"{device_coordinator.data.serial_number}-current_app"

    @property
    @override
    def options(self) -> list[str]:
        """Return the widgets of the device."""
        if not (apps := self.coordinator.data):
            return []
        return widget_options(apps)

    @property
    @override
    def native_value(self) -> str | None:
        """Return the widget currently shown on the device."""
        if not (apps := self.coordinator.data):
            return None
        return current_widget(apps)
