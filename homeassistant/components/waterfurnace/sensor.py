"""Support for Waterfurnace."""

from __future__ import annotations

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import DOMAIN, WaterFurnaceConfigEntry
from .coordinator import WaterFurnaceCoordinator

SENSORS = [
    SensorEntityDescription(
        key="mode",
        translation_key="mode",
    ),
    SensorEntityDescription(
        key="totalunitpower",
        translation_key="total_unit_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstatactivesetpoint",
        translation_key="tstat_active_setpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="leavingairtemp",
        translation_key="leaving_air_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstatroomtemp",
        translation_key="room_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="enteringwatertemp",
        translation_key="entering_water_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstathumidsetpoint",
        translation_key="tstat_humid_setpoint",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstatrelativehumidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="compressorpower",
        translation_key="compressor_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="fanpower",
        translation_key="fan_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="auxpower",
        translation_key="aux_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="looppumppower",
        translation_key="loop_pump_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="actualcompressorspeed",
        translation_key="actual_compressor_speed",
    ),
    SensorEntityDescription(
        key="airflowcurrentspeed",
        translation_key="airflow_current_speed",
    ),
    SensorEntityDescription(
        key="tstatdehumidsetpoint",
        translation_key="tstat_dehumid_setpoint",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="leavingwatertemp",
        translation_key="leaving_water_temp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstatheatingsetpoint",
        translation_key="tstat_heating_setpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tstatcoolingsetpoint",
        translation_key="tstat_cooling_setpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="waterflowrate",
        translation_key="water_flow_rate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WaterFurnaceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Waterfurnace sensors from a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        WaterFurnaceSensor(coordinator, description) for description in SENSORS
    )


class WaterFurnaceSensor(CoordinatorEntity[WaterFurnaceCoordinator], SensorEntity):
    """Implementing the Waterfurnace sensor."""

    entity_description: SensorEntityDescription
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WaterFurnaceCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        # This ensures that the sensors are isolated per waterfurnace unit
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"wf_{slugify(coordinator.unit)}_{slugify(description.key)}"
        )
        self._attr_unique_id = f"{coordinator.unit}_{description.key}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unit)},
            manufacturer="WaterFurnace",
            name="WaterFurnace System",
        )

        if coordinator.device_metadata:
            if coordinator.device_metadata.description:
                # Eg. Series 7
                device_info["model"] = coordinator.device_metadata.description
            if coordinator.device_metadata.awlabctypedesc:
                # Eg. Series 7, 5 Ton
                device_info["name"] = coordinator.device_metadata.awlabctypedesc

        self._attr_device_info = device_info

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return getattr(self.coordinator.data, self.entity_description.key, None)
