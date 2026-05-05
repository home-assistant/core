"""Platform for Lunatone sensor integration."""

from typing import Final

from lunatone_rest_api_client.models import SensorAddressType, SensorType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LunatoneConfigEntry, LunatoneSensorsDataUpdateCoordinator

PARALLEL_UPDATES = 0
SENSOR_TYPES: Final[dict[str, SensorEntityDescription]] = {
    SensorType.AIR_HUMIDITY: SensorEntityDescription(
        key="air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorType.AIR_PRESSURE: SensorEntityDescription(
        key="air_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorType.AIR_QUALITY: SensorEntityDescription(
        key="air_quality",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorType.ECO2: SensorEntityDescription(
        key="eco2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorType.LIGHT: SensorEntityDescription(
        key="light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorType.TEMPERATURE: SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorType.VOC: SensorEntityDescription(
        key="voc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lunatone sensors from the config entry."""
    coordinator_sensors = config_entry.runtime_data.coordinator_sensors

    assert config_entry.unique_id is not None

    entities = []
    for sensor_id, sensor_data in coordinator_sensors.data.items():
        if description := SENSOR_TYPES.get(sensor_data.data.type, None):
            entities.append(
                LunatoneSensor(
                    coordinator_sensors, description, sensor_id, config_entry.unique_id
                )
            )

    async_add_entities(entities)


class LunatoneSensor(
    CoordinatorEntity[LunatoneSensorsDataUpdateCoordinator], SensorEntity
):
    """Representation of a Lunatone Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LunatoneSensorsDataUpdateCoordinator,
        description: SensorEntityDescription,
        sensor_id: int,
        config_entry_unique_id: str,
    ) -> None:
        """Initialize a Lunatone Sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._config_entry_unique_id = config_entry_unique_id
        self._sensor_id = sensor_id
        self._sensor = self.coordinator.data.get(self._sensor_id)

        self._attr_unique_id = (
            f"{config_entry_unique_id}-sensor{sensor_id}-{description.key}"
        )
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._config_entry_unique_id)},
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
        return self._sensor.name if self._sensor else f"Sensor {self._sensor_id}"

    @property
    def native_value(self) -> float | None:
        """Return the measurement value of the sensor."""
        return self._sensor.data.value if self._sensor else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sensor = self.coordinator.data[self._sensor_id]
        self.async_write_ha_state()
