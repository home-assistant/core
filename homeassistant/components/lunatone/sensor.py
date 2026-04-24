"""Platform for Lunatone sensor integration."""

from lunatone_rest_api_client.models import (
    SensorAddressType,
    SensorMeasurementUnit,
    SensorType,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LunatoneConfigEntry, LunatoneSensorsDataUpdateCoordinator

SENSOR_DEVICE_CLASS_MAPPING: dict[SensorType, SensorDeviceClass] = {
    SensorType.TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    SensorType.AIR_HUMIDITY: SensorDeviceClass.HUMIDITY,
    SensorType.AIR_PRESSURE: SensorDeviceClass.PRESSURE,
    SensorType.ECO2: SensorDeviceClass.CO2,
    SensorType.VOC: SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
    SensorType.AIR_QUALITY: SensorDeviceClass.AQI,
    SensorType.LIGHT: SensorDeviceClass.ILLUMINANCE,
}

SENSOR_UNIT_MAPPING: dict[SensorMeasurementUnit, str | None] = {
    SensorMeasurementUnit.DEGREE_CELSIUS: UnitOfTemperature.CELSIUS,
    SensorMeasurementUnit.PERCENT: PERCENTAGE,
    SensorMeasurementUnit.HECTOPASCAL: UnitOfPressure.HPA,
    SensorMeasurementUnit.PARTS_PER_MILLION: CONCENTRATION_PARTS_PER_MILLION,
    SensorMeasurementUnit.PARTS_PER_BILLION: CONCENTRATION_PARTS_PER_BILLION,
    SensorMeasurementUnit.INDOOR_AIR_QUALITY: None,
    SensorMeasurementUnit.LUX: LIGHT_LUX,
}

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lunatone sensors from the config entry."""
    coordinator_sensors = config_entry.runtime_data.coordinator_sensors

    assert config_entry.unique_id is not None

    async_add_entities(
        [
            LunatoneSensor(coordinator_sensors, sensor_id, config_entry.unique_id)
            for sensor_id, sensor_data in coordinator_sensors.data.items()
            if sensor_data.data.type in SENSOR_DEVICE_CLASS_MAPPING
        ]
    )


class LunatoneSensor(
    CoordinatorEntity[LunatoneSensorsDataUpdateCoordinator], SensorEntity
):
    """Representation of a Lunatone Sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: LunatoneSensorsDataUpdateCoordinator,
        sensor_id: int,
        config_entry_unique_id: str,
    ) -> None:
        """Initialize a Lunatone Sensor."""
        super().__init__(coordinator=coordinator)
        self._sensor_id = sensor_id
        self._config_entry_unique_id = config_entry_unique_id
        self._sensor = self.coordinator.data.get(self._sensor_id)
        self._attr_unique_id = f"{config_entry_unique_id}-sensor{sensor_id}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._config_entry_unique_id))},
        )
        if (
            self._sensor
            and self._sensor.data.address_type == SensorAddressType.DALI
            and self._sensor.data.dali_sensor_address
        ):
            device_info = DeviceInfo(
                identifiers={
                    (
                        DOMAIN,
                        f"{self._config_entry_unique_id}"
                        f"-line{self._sensor.data.dali_sensor_address.line}"
                        f"-d24-address{self._sensor.data.dali_sensor_address.address}",
                    )
                },
                name=(
                    f"DALI Line {self._sensor.data.dali_sensor_address.line}"
                    f" - A{self._sensor.data.dali_sensor_address.address}\u00b2"
                ),
                via_device=(DOMAIN, str(self._config_entry_unique_id)),
            )
        self._attr_device_info = device_info

    @property
    def name(self) -> str:
        """Return the display name of this sensor."""
        return self._sensor.name if self._sensor else ""

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the sensor."""
        return (
            SENSOR_DEVICE_CLASS_MAPPING.get(self._sensor.data.type)
            if self._sensor
            else None
        )

    @property
    def native_value(self) -> float | None:
        """Return the measurement value of the sensor."""
        return self._sensor.data.value if self._sensor else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement for the sensor."""
        return SENSOR_UNIT_MAPPING.get(self._sensor.data.unit) if self._sensor else None
