"""Support for OpenAQ sensors."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_conversion import DistanceConverter

from .const import ATTRIBUTION, DOMAIN
from .coordinator import (
    OpenAQConfigEntry,
    OpenAQDataUpdateCoordinator,
    OpenAQLocationData,
)

_LOGGER = logging.getLogger(__name__)

DISTANCE_FROM_HOME = "distance_from_home"


@dataclass(frozen=True, kw_only=True)
class OpenAQSensorEntityDescription(SensorEntityDescription):
    """Description for an OpenAQ sensor entity."""


SENSOR_DESCRIPTIONS: dict[str, OpenAQSensorEntityDescription] = {
    "pm1": OpenAQSensorEntityDescription(
        key="pm1",
        translation_key="pm1",
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "pm25": OpenAQSensorEntityDescription(
        key="pm25",
        translation_key="pm25",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "pm10": OpenAQSensorEntityDescription(
        key="pm10",
        translation_key="pm10",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "co": OpenAQSensorEntityDescription(
        key="co",
        translation_key="co",
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    "co2": OpenAQSensorEntityDescription(
        key="co2",
        translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "no2": OpenAQSensorEntityDescription(
        key="no2",
        translation_key="no2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "o3": OpenAQSensorEntityDescription(
        key="o3",
        translation_key="o3",
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "so2": OpenAQSensorEntityDescription(
        key="so2",
        translation_key="so2",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "no": OpenAQSensorEntityDescription(
        key="no",
        translation_key="no",
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "nox": OpenAQSensorEntityDescription(
        key="nox",
        translation_key="nox",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "bc": OpenAQSensorEntityDescription(
        key="bc",
        translation_key="bc",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
}

DISTANCE_SENSOR_DESCRIPTION = OpenAQSensorEntityDescription(
    key=DISTANCE_FROM_HOME,
    translation_key=DISTANCE_FROM_HOME,
    name="Distance from Home Assistant",
    device_class=SensorDeviceClass.DISTANCE,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    native_unit_of_measurement=UnitOfLength.KILOMETERS,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenAQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenAQ sensors."""
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        async_add_entities(
            [
                OpenAQSensor(coordinator, SENSOR_DESCRIPTIONS[parameter])
                for parameter in coordinator.data.measurements
                if parameter in SENSOR_DESCRIPTIONS
            ]
            + [OpenAQSensor(coordinator, DISTANCE_SENSOR_DESCRIPTION)],
            config_subentry_id=subentry_id,
        )
        for parameter in coordinator.data.measurements:
            if parameter not in SENSOR_DESCRIPTIONS:
                _LOGGER.debug("Ignoring unsupported OpenAQ parameter: %s", parameter)


class OpenAQSensor(CoordinatorEntity[OpenAQDataUpdateCoordinator], SensorEntity):
    """Representation of an OpenAQ sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: OpenAQSensorEntityDescription

    def __init__(
        self,
        coordinator: OpenAQDataUpdateCoordinator,
        entity_description: OpenAQSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.location_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.location_id))},
            name=coordinator.data.name,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if self.entity_description.key == DISTANCE_FROM_HOME:
            distance_to_home = self.coordinator.data.distance_to_home
            if distance_to_home is None:
                return None
            return DistanceConverter.convert(
                distance_to_home,
                UnitOfLength.METERS,
                self.hass.config.units.length_unit,
            )

        measurement = self.coordinator.data.measurements.get(
            self.entity_description.key
        )
        return measurement.value if measurement is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        if self.entity_description.key == DISTANCE_FROM_HOME:
            return self.hass.config.units.length_unit

        measurement = self.coordinator.data.measurements.get(
            self.entity_description.key
        )
        if measurement is None:
            return None
        return measurement.unit


__all__ = ["SENSOR_DESCRIPTIONS", "OpenAQLocationData", "OpenAQSensor"]
