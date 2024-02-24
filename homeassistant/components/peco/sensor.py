"""Sensor component for PECO outage counter."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import PECOCoordinatorData
from .const import ATTR_CONTENT, CONF_COUNTY, DOMAIN


@dataclass(frozen=True)
class PECOSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[PECOCoordinatorData], int | str]
    attribute_fn: Callable[[PECOCoordinatorData], dict[str, str]]


@dataclass(frozen=True)
class PECOSensorEntityDescription(
    SensorEntityDescription, PECOSensorEntityDescriptionMixin
):
    """Description for PECO sensor."""


PARALLEL_UPDATES: Final = 0
SENSOR_LIST: tuple[PECOSensorEntityDescription, ...] = (
    PECOSensorEntityDescription(
        key="customers_out",
        translation_key="customers_out",
        value_fn=lambda data: int(data.outages.customers_out),
        attribute_fn=lambda data: {},
        icon="mdi:power-plug-off",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PECOSensorEntityDescription(
        key="percent_customers_out",
        translation_key="percent_customers_out",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: int(data.outages.percent_customers_out),
        attribute_fn=lambda data: {},
        icon="mdi:power-plug-off",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PECOSensorEntityDescription(
        key="outage_count",
        translation_key="outage_count",
        value_fn=lambda data: int(data.outages.outage_count),
        attribute_fn=lambda data: {},
        icon="mdi:power-plug-off",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PECOSensorEntityDescription(
        key="customers_served",
        translation_key="customers_served",
        value_fn=lambda data: int(data.outages.customers_served),
        attribute_fn=lambda data: {},
        icon="mdi:power-plug-off",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PECOSensorEntityDescription(
        key="map_alert",
        translation_key="map_alert",
        value_fn=lambda data: str(data.alerts.alert_title),
        attribute_fn=lambda data: {ATTR_CONTENT: data.alerts.alert_content},
        icon="mdi:alert",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    county: str = config_entry.data[CONF_COUNTY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["outage_count"]

    async_add_entities(
        PecoSensor(sensor, county, coordinator) for sensor in SENSOR_LIST
    )


class PecoSensor(
    CoordinatorEntity[DataUpdateCoordinator[PECOCoordinatorData]], SensorEntity
):
    """PECO outage counter sensor."""

    entity_description: PECOSensorEntityDescription

    _attr_has_entity_name = True

    def __init__(
        self,
        description: PECOSensorEntityDescription,
        county: str,
        coordinator: DataUpdateCoordinator[PECOCoordinatorData],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{county}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, county)}, name=county.capitalize()
        )
        self.entity_description = description

    @property
    def native_value(self) -> int | str:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return state attributes for the sensor."""
        return self.entity_description.attribute_fn(self.coordinator.data)
