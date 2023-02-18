"""waterkotte sensor platform."""

from pywaterkotte.ecotouch import EcotouchTags, TagData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcotouchCoordinator
from .const import DOMAIN
from .entity import EcotouchEntity

SENSOR_DESCRIPTIONS = {
    EcotouchTags.OUTSIDE_TEMPERATURE: SensorEntityDescription(
        key="outside_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:sun-thermometer-outline",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.OUTSIDE_TEMPERATURE_1H: SensorEntityDescription(
        key="outside_temperature_1h",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:sun-thermometer-outline",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.OUTSIDE_TEMPERATURE_24H: SensorEntityDescription(
        key="outside_temperature_24h",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:sun-thermometer-outline",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.SOURCE_IN_TEMPERATURE: SensorEntityDescription(
        key="source_in_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.SOURCE_OUT_TEMPERATURE: SensorEntityDescription(
        key="source_out_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.EVAPORATION_TEMPERATURE: SensorEntityDescription(
        key="evaporation_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.SUCTION_LINE_TEMPERATURE: SensorEntityDescription(
        key="suction_line_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.EVAPORATION_PRESSURE: SensorEntityDescription(
        key="evaporation_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfPressure.BAR,
    ),
    EcotouchTags.RETURN_TEMPERATURE: SensorEntityDescription(
        key="return_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.FLOW_TEMPERATURE: SensorEntityDescription(
        key="flow_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.CONDENSATION_TEMPERATURE: SensorEntityDescription(
        key="condensation_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.BUFFER_TANK_TEMPERATURE: SensorEntityDescription(
        key="buffer_tank_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.ROOM_TEMPERATURE: SensorEntityDescription(
        key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.ROOM_TEMPERATURE_1H: SensorEntityDescription(
        key="room_temperature_1h",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.HOT_WATER_TEMPERATURE: SensorEntityDescription(
        key="hot_water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.HOT_WATER_TEMPERATURE_SETPOINT: SensorEntityDescription(
        key="hot_water_temperature_setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.HEATING_TEMPERATURE: SensorEntityDescription(
        key="heating_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.HEATING_TEMPERATURE_SETPOINT: SensorEntityDescription(
        key="heating_temperature_setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer-water",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcotouchTags.COMPRESSOR_ELECTRIC_CONSUMPTION_YEAR: SensorEntityDescription(
        key="compressor_power_consumption_year",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    EcotouchTags.SOURCEPUMP_ELECTRIC_CONSUMPTION_YEAR: SensorEntityDescription(
        key="sourcepump_power_consumption_year",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    EcotouchTags.ELECTRICAL_HEATER_ELECTRIC_CONSUMPTION_YEAR: SensorEntityDescription(
        key="electrical_heater_power_consumption_year",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    EcotouchTags.HEATING_ENERGY_PRODUCED_YEAR: SensorEntityDescription(
        key="heating_energy_produced_year",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    EcotouchTags.HOT_WATER_ENERGY_PRODUCED_YEAR: SensorEntityDescription(
        key="hot_water_energy_produced_year",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
    ),
    EcotouchTags.ELECTRICAL_POWER: SensorEntityDescription(
        key="electrical_power",
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    EcotouchTags.THERMAL_POWER: SensorEntityDescription(
        key="thermal_power",
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    EcotouchTags.COOLING_POWER: SensorEntityDescription(
        key="cooling_power",
        device_class=SensorDeviceClass.POWER,
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create waterkotte_heatpump sensor entities."""
    coordinator: EcotouchCoordinator = hass.data[DOMAIN][entry.entry_id]

    def get_device_info() -> DeviceInfo:
        """Create DeviceInfo object."""
        heatpump_type = coordinator.heatpump.read_value(EcotouchTags.HEATPUMP_TYPE)
        serial_nr = coordinator.heatpump.read_value(EcotouchTags.SERIAL_NUMBER)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{serial_nr:08d}")},
            name="heatpump",
            manufacturer="Waterkotte GmbH",
            model=coordinator.heatpump.decode_heatpump_series(heatpump_type),
            sw_version=coordinator.heatpump.read_value(EcotouchTags.FIRMWARE_VERSION),
            hw_version=coordinator.heatpump.read_value(EcotouchTags.HARDWARE_REVISION),
            configuration_url=f'http://{entry.data.get("host")}',
        )

    device_info = await hass.async_add_executor_job(get_device_info)

    entities = [
        EcotouchSensor(entry, coordinator, tag, sensor_config, device_info)
        for tag, sensor_config in SENSOR_DESCRIPTIONS.items()
    ]

    async_add_entities(entities)


class EcotouchSensor(EcotouchEntity, SensorEntity):
    """waterkotte_heatpump Sensor class."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: EcotouchCoordinator,
        tag: TagData,
        sensor_config: SensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tag, config_entry, sensor_config, device_info)
