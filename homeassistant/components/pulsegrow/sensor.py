"""Sensor platform for PulseGrow integration."""

from __future__ import annotations

from dataclasses import dataclass

from aiopulsegrow import DeviceType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PulseGrowConfigEntry
from .const import DOMAIN
from .coordinator import PulseGrowDataUpdateCoordinator
from .entity import PulseGrowDeviceEntity, PulseGrowHubEntity, PulseGrowSensorEntity


@dataclass(frozen=True, kw_only=True)
class PulseGrowSensorEntityDescription(SensorEntityDescription):
    """Describes a PulseGrow sensor entity."""


# Device sensor entity descriptions (from most_recent_data_point)
DEVICE_SENSOR_DESCRIPTIONS: tuple[PulseGrowSensorEntityDescription, ...] = (
    PulseGrowSensorEntityDescription(
        key="temperature_f",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PulseGrowSensorEntityDescription(
        key="humidity_rh",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PulseGrowSensorEntityDescription(
        key="air_pressure",
        translation_key="air_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PulseGrowSensorEntityDescription(
        key="vpd",
        translation_key="vpd",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PulseGrowSensorEntityDescription(
        key="dp_f",
        translation_key="dew_point",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PulseGrowSensorEntityDescription(
        key="co2",
        translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PulseGrowSensorEntityDescription(
        key="light_lux",
        translation_key="light",
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PulseGrowSensorEntityDescription(
        key="signal_strength",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement="dBm",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    PulseGrowSensorEntityDescription(
        key="battery_v",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
)

# Pro Light sensor descriptions (from pro_light_reading_preview)
PRO_LIGHT_SENSOR_DESCRIPTIONS: tuple[PulseGrowSensorEntityDescription, ...] = (
    PulseGrowSensorEntityDescription(
        key="ppfd",
        translation_key="ppfd",
        native_unit_of_measurement="μmol/s/m²",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PulseGrowSensorEntityDescription(
        key="dli",
        translation_key="dli",
        native_unit_of_measurement="mol/d/m²",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# Hub sensor descriptions
HUB_SENSOR_DESCRIPTIONS: tuple[PulseGrowSensorEntityDescription, ...] = (
    PulseGrowSensorEntityDescription(
        key="mac_address",
        translation_key="mac_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)

# Mapping of sensor data point param names to sensor descriptions
# These are hub-connected sensors (VWC, EC, pH, etc.)
SENSOR_PARAM_DESCRIPTIONS: dict[str, PulseGrowSensorEntityDescription] = {
    "temperature": PulseGrowSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        # Unit comes from API measuring_unit field
    ),
    "humidity": PulseGrowSensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "vpd": PulseGrowSensorEntityDescription(
        key="vpd",
        translation_key="vpd",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "water_content": PulseGrowSensorEntityDescription(
        key="water_content",
        translation_key="water_content",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pore_water_ec": PulseGrowSensorEntityDescription(
        key="pore_water_ec",
        translation_key="pore_water_ec",
        state_class=SensorStateClass.MEASUREMENT,
        # Unit comes from API (typically dS/m or mS/cm)
    ),
    "bulk_ec": PulseGrowSensorEntityDescription(
        key="bulk_ec",
        translation_key="bulk_ec",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ph": PulseGrowSensorEntityDescription(
        key="ph",
        translation_key="ph",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ec": PulseGrowSensorEntityDescription(
        key="ec",
        translation_key="ec",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ppfd": PulseGrowSensorEntityDescription(
        key="ppfd",
        translation_key="ppfd",
        native_unit_of_measurement="μmol/s/m²",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "co2": PulseGrowSensorEntityDescription(
        key="co2",
        translation_key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PulseGrowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PulseGrow sensor entities."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = []

    # Create device sensors
    for device_id, device in coordinator.data.devices.items():
        data_point = device.most_recent_data_point
        if data_point:
            entities.extend(
                PulseGrowDeviceSensor(coordinator, device_id, description)
                for description in DEVICE_SENSOR_DESCRIPTIONS
                if getattr(data_point, description.key, None) is not None
            )

        # Create Pro Light sensors (from pro_light_reading_preview) - Pulse Pro only
        if (
            device.device_type is not None
            and int(device.device_type) == DeviceType.PULSE_PRO
        ):
            pro_light = device.pro_light_reading_preview
            if pro_light:
                entities.extend(
                    PulseGrowProLightSensor(coordinator, device_id, description)
                    for description in PRO_LIGHT_SENSOR_DESCRIPTIONS
                    if getattr(pro_light, description.key, None) is not None
                )

    # Create hub sensors
    for hub_id, hub in coordinator.data.hubs.items():
        entities.extend(
            PulseGrowHubSensor(coordinator, hub_id, description)
            for description in HUB_SENSOR_DESCRIPTIONS
            if getattr(hub, description.key, None) is not None
        )

    # Create hub-connected sensor entities (VWC, EC, pH, etc.)
    for sensor_id, sensor in coordinator.data.sensors.items():
        sensor_data_point = sensor.most_recent_data_point
        if not sensor_data_point or not sensor_data_point.data_point_values:
            continue

        for data_value in sensor_data_point.data_point_values:
            param_name = data_value.param_name
            if not param_name:
                continue
            # Normalize param name to lowercase for lookup
            param_name_lower = param_name.lower()
            if param_name_lower in SENSOR_PARAM_DESCRIPTIONS:
                entities.append(
                    PulseGrowHubConnectedSensor(
                        coordinator,
                        sensor_id,
                        param_name,  # Keep original for display/matching
                        SENSOR_PARAM_DESCRIPTIONS[param_name_lower],
                        data_value.measuring_unit,
                    )
                )

    async_add_entities(entities)


class PulseGrowDeviceSensor(PulseGrowDeviceEntity, SensorEntity):
    """Sensor entity for PulseGrow device readings."""

    entity_description: PulseGrowSensorEntityDescription

    def __init__(
        self,
        coordinator: PulseGrowDataUpdateCoordinator,
        device_id: str,
        description: PulseGrowSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        device = self.coordinator.data.devices.get(self._entity_id)
        if not device or not device.most_recent_data_point:
            return None
        return getattr(device.most_recent_data_point, self.entity_description.key, None)


class PulseGrowProLightSensor(PulseGrowDeviceEntity, SensorEntity):
    """Sensor entity for PulseGrow Pro Light readings."""

    entity_description: PulseGrowSensorEntityDescription

    def __init__(
        self,
        coordinator: PulseGrowDataUpdateCoordinator,
        device_id: str,
        description: PulseGrowSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        device = self.coordinator.data.devices.get(self._entity_id)
        if not device or not device.pro_light_reading_preview:
            return None
        return getattr(
            device.pro_light_reading_preview, self.entity_description.key, None
        )


class PulseGrowHubSensor(PulseGrowHubEntity, SensorEntity):
    """Sensor entity for PulseGrow hub readings."""

    entity_description: PulseGrowSensorEntityDescription

    def __init__(
        self,
        coordinator: PulseGrowDataUpdateCoordinator,
        hub_id: str,
        description: PulseGrowSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, hub_id)
        self.entity_description = description
        self._attr_unique_id = f"{hub_id}_{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, hub_id)}}

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self._entity_id not in self.coordinator.data.hubs:
            return None
        return getattr(self.hub, self.entity_description.key, None)


class PulseGrowHubConnectedSensor(PulseGrowSensorEntity, SensorEntity):
    """Sensor entity for PulseGrow hub-connected sensors (VWC, EC, pH, etc.)."""

    entity_description: PulseGrowSensorEntityDescription

    def __init__(
        self,
        coordinator: PulseGrowDataUpdateCoordinator,
        sensor_id: str,
        param_name: str,
        description: PulseGrowSensorEntityDescription,
        measuring_unit: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor_id)
        self.entity_description = description
        self._param_name = param_name
        self._attr_unique_id = f"{sensor_id}_{param_name}"

        # Use measuring_unit from API if not set in description
        if measuring_unit and not description.native_unit_of_measurement:
            self._attr_native_unit_of_measurement = measuring_unit

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        sensor = self.coordinator.data.sensors.get(self._entity_id)
        if not sensor or not sensor.most_recent_data_point:
            return None

        data_point = sensor.most_recent_data_point
        if not data_point.data_point_values:
            return None

        # Find the matching param value (case-insensitive comparison)
        param_name_lower = self._param_name.lower()
        for data_value in data_point.data_point_values:
            if (
                data_value.param_name
                and data_value.param_name.lower() == param_name_lower
            ):
                try:
                    return (
                        float(data_value.param_value)
                        if data_value.param_value
                        else None
                    )
                except (ValueError, TypeError):
                    return data_value.param_value

        return None
