"""Support for Toon sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CURRENCY_EUR, DOMAIN, VOLUME_CM3, VOLUME_LMIN
from .coordinator import ToonDataUpdateCoordinator
from .models import (
    ToonBoilerDeviceEntity,
    ToonDisplayDeviceEntity,
    ToonElectricityMeterDeviceEntity,
    ToonEntity,
    ToonGasMeterDeviceEntity,
    ToonRequiredKeysMixin,
    ToonSolarDeviceEntity,
    ToonWaterMeterDeviceEntity,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Toon sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        description.cls(coordinator, description) for description in SENSOR_ENTITIES
    ]

    if coordinator.data.agreement.is_toon_solar:
        entities.extend(
            [
                description.cls(coordinator, description)
                for description in SENSOR_ENTITIES_SOLAR
            ]
        )

    if coordinator.data.thermostat.have_opentherm_boiler:
        entities.extend(
            [
                description.cls(coordinator, description)
                for description in SENSOR_ENTITIES_BOILER
            ]
        )

    async_add_entities(entities, True)


class ToonSensor(ToonEntity, SensorEntity):
    """Defines a Toon sensor."""

    entity_description: ToonSensorEntityDescription

    def __init__(
        self,
        coordinator: ToonDataUpdateCoordinator,
        description: ToonSensorEntityDescription,
    ) -> None:
        """Initialize the Toon sensor."""
        self.entity_description = description
        super().__init__(coordinator)

        self._attr_unique_id = (
            # This unique ID is a bit ugly and contains unneeded information.
            # It is here for legacy / backward compatible reasons.
            f"{DOMAIN}_{coordinator.data.agreement.agreement_id}_sensor_{description.key}"
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        section = getattr(self.coordinator.data, self.entity_description.section)
        return getattr(section, self.entity_description.measurement)


class ToonElectricityMeterDeviceSensor(ToonSensor, ToonElectricityMeterDeviceEntity):
    """Defines a Electricity Meter sensor."""


class ToonGasMeterDeviceSensor(ToonSensor, ToonGasMeterDeviceEntity):
    """Defines a Gas Meter sensor."""


class ToonWaterMeterDeviceSensor(ToonSensor, ToonWaterMeterDeviceEntity):
    """Defines a Water Meter sensor."""


class ToonSolarDeviceSensor(ToonSensor, ToonSolarDeviceEntity):
    """Defines a Solar sensor."""


class ToonBoilerDeviceSensor(ToonSensor, ToonBoilerDeviceEntity):
    """Defines a Boiler sensor."""


class ToonDisplayDeviceSensor(ToonSensor, ToonDisplayDeviceEntity):
    """Defines a Display sensor."""


@dataclass
class ToonSensorRequiredKeysMixin(ToonRequiredKeysMixin):
    """Mixin for sensor required keys."""

    cls: type[ToonSensor]


@dataclass
class ToonSensorEntityDescription(SensorEntityDescription, ToonSensorRequiredKeysMixin):
    """Describes Toon sensor entity."""


SENSOR_ENTITIES: tuple[ToonSensorEntityDescription, ...] = (
    ToonSensorEntityDescription(
        key="current_display_temperature",
        name="Temperature",
        section="thermostat",
        measurement="current_display_temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        cls=ToonDisplayDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="current_humidity",
        name="Humidity",
        section="thermostat",
        measurement="current_humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        cls=ToonDisplayDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_average",
        name="Average Gas Usage",
        section="gas_usage",
        measurement="average",
        native_unit_of_measurement=VOLUME_CM3,
        icon="mdi:gas-cylinder",
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_average_daily",
        name="Average Daily Gas Usage",
        section="gas_usage",
        measurement="day_average",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        entity_registry_enabled_default=False,
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_daily_usage",
        name="Gas Usage Today",
        section="gas_usage",
        measurement="day_usage",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_daily_cost",
        name="Gas Cost Today",
        section="gas_usage",
        measurement="day_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=CURRENCY_EUR,
        icon="mdi:gas-cylinder",
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_meter_reading",
        name="Gas Meter",
        section="gas_usage",
        measurement="meter",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.GAS,
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_value",
        name="Current Gas Usage",
        section="gas_usage",
        measurement="current",
        native_unit_of_measurement=VOLUME_CM3,
        icon="mdi:gas-cylinder",
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_average",
        name="Average Power Usage",
        section="power_usage",
        measurement="average",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_average_daily",
        name="Average Daily Energy Usage",
        section="power_usage",
        measurement="day_average",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_daily_cost",
        name="Energy Cost Today",
        section="power_usage",
        measurement="day_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=CURRENCY_EUR,
        icon="mdi:power-plug",
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_daily_value",
        name="Energy Usage Today",
        section="power_usage",
        measurement="day_usage",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_meter_reading",
        name="Electricity Meter Feed IN Tariff 1",
        section="power_usage",
        measurement="meter_high",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_meter_reading_low",
        name="Electricity Meter Feed IN Tariff 2",
        section="power_usage",
        measurement="meter_low",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_value",
        name="Current Power Usage",
        section="power_usage",
        measurement="current",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_meter_reading_produced",
        name="Electricity Meter Feed OUT Tariff 1",
        section="power_usage",
        measurement="meter_produced_high",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_meter_reading_low_produced",
        name="Electricity Meter Feed OUT Tariff 2",
        section="power_usage",
        measurement="meter_produced_low",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="water_average",
        name="Average Water Usage",
        section="water_usage",
        measurement="average",
        native_unit_of_measurement=VOLUME_LMIN,
        icon="mdi:water",
        entity_registry_enabled_default=False,
        cls=ToonWaterMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="water_average_daily",
        name="Average Daily Water Usage",
        section="water_usage",
        measurement="day_average",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        icon="mdi:water",
        entity_registry_enabled_default=False,
        cls=ToonWaterMeterDeviceSensor,
        device_class=SensorDeviceClass.WATER,
    ),
    ToonSensorEntityDescription(
        key="water_daily_usage",
        name="Water Usage Today",
        section="water_usage",
        measurement="day_usage",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        icon="mdi:water",
        entity_registry_enabled_default=False,
        cls=ToonWaterMeterDeviceSensor,
        device_class=SensorDeviceClass.WATER,
    ),
    ToonSensorEntityDescription(
        key="water_meter_reading",
        name="Water Meter",
        section="water_usage",
        measurement="meter",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        icon="mdi:water",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        cls=ToonWaterMeterDeviceSensor,
        device_class=SensorDeviceClass.WATER,
    ),
    ToonSensorEntityDescription(
        key="water_value",
        name="Current Water Usage",
        section="water_usage",
        measurement="current",
        native_unit_of_measurement=VOLUME_LMIN,
        icon="mdi:water-pump",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        cls=ToonWaterMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="water_daily_cost",
        name="Water Cost Today",
        section="water_usage",
        measurement="day_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=CURRENCY_EUR,
        icon="mdi:water-pump",
        entity_registry_enabled_default=False,
        cls=ToonWaterMeterDeviceSensor,
    ),
)

SENSOR_ENTITIES_SOLAR: tuple[ToonSensorEntityDescription, ...] = (
    ToonSensorEntityDescription(
        key="solar_value",
        name="Current Solar Power Production",
        section="power_usage",
        measurement="current_solar",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_maximum",
        name="Max Solar Power Production Today",
        section="power_usage",
        measurement="day_max_solar",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_produced",
        name="Solar Power Production to Grid",
        section="power_usage",
        measurement="current_produced",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_usage_day_produced_solar",
        name="Solar Energy Produced Today",
        section="power_usage",
        measurement="day_produced_solar",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_usage_day_to_grid_usage",
        name="Energy Produced To Grid Today",
        section="power_usage",
        measurement="day_to_grid_usage",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_usage_day_from_grid_usage",
        name="Energy Usage From Grid Today",
        section="power_usage",
        measurement="day_from_grid_usage",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_registry_enabled_default=False,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_average_produced",
        name="Average Solar Power Production to Grid",
        section="power_usage",
        measurement="average_produced",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_usage_current_covered_by_solar",
        name="Current Power Usage Covered By Solar",
        section="power_usage",
        measurement="current_covered_by_solar",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:solar-power",
        state_class=SensorStateClass.MEASUREMENT,
        cls=ToonSolarDeviceSensor,
    ),
)

SENSOR_ENTITIES_BOILER: tuple[ToonSensorEntityDescription, ...] = (
    ToonSensorEntityDescription(
        key="thermostat_info_current_modulation_level",
        name="Boiler Modulation Level",
        section="thermostat",
        measurement="current_modulation_level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        cls=ToonBoilerDeviceSensor,
    ),
)
