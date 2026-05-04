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
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import (
    OpenAQConfigEntry,
    OpenAQDataUpdateCoordinator,
    OpenAQLocationData,
)

_LOGGER = logging.getLogger(__name__)

UNIT_MAP = {
    "µg/m³": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "µg/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "ug/m³": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "ug/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "μg/m³": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "μg/m3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "mg/m³": CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    "mg/m3": CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    "ppm": CONCENTRATION_PARTS_PER_MILLION,
    "ppb": CONCENTRATION_PARTS_PER_BILLION,
}


@dataclass(frozen=True, kw_only=True)
class OpenAQSensorEntityDescription(SensorEntityDescription):
    """Description for an OpenAQ sensor entity."""


SENSOR_DESCRIPTIONS: dict[str, OpenAQSensorEntityDescription] = {
    "pm1": OpenAQSensorEntityDescription(
        key="pm1",
        translation_key="pm1",
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pm25": OpenAQSensorEntityDescription(
        key="pm25",
        translation_key="pm25",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pm10": OpenAQSensorEntityDescription(
        key="pm10",
        translation_key="pm10",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "co": OpenAQSensorEntityDescription(
        key="co",
        translation_key="co",
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "co2": OpenAQSensorEntityDescription(
        key="co2",
        translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "no2": OpenAQSensorEntityDescription(
        key="no2",
        translation_key="no2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "o3": OpenAQSensorEntityDescription(
        key="o3",
        translation_key="o3",
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "so2": OpenAQSensorEntityDescription(
        key="so2",
        translation_key="so2",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "no": OpenAQSensorEntityDescription(
        key="no",
        translation_key="no",
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "nox": OpenAQSensorEntityDescription(
        key="nox",
        translation_key="nox",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "bc": OpenAQSensorEntityDescription(
        key="bc",
        translation_key="bc",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenAQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenAQ sensors."""
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        async_add_entities(
            (
                OpenAQSensor(coordinator, SENSOR_DESCRIPTIONS[parameter])
                for parameter in coordinator.data.measurements
                if parameter in SENSOR_DESCRIPTIONS
            ),
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
        return self.coordinator.data.measurements[self.entity_description.key].value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        unit = self.coordinator.data.measurements[self.entity_description.key].unit
        if unit is None:
            return None
        return UNIT_MAP.get(unit, unit)


__all__ = ["SENSOR_DESCRIPTIONS", "OpenAQLocationData", "OpenAQSensor"]
