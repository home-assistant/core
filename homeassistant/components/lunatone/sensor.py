"""Platform for Lunatone sensor integration."""

from typing import Final, override

from lunatone_rest_api_client import Sensor
from lunatone_rest_api_client.models import LineStatus, SensorAddressType, SensorType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    EntityCategory,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    LunatoneConfigEntry,
    LunatoneInfoDataUpdateCoordinator,
    LunatoneSensorsDataUpdateCoordinator,
)

DALI_LINE_STATUS_SENSOR_MAPPING: dict[str, str] = {
    LineStatus.LOW_POWER: "low_power",
    LineStatus.NO_POWER: "no_power",
    LineStatus.NOT_REACHABLE: "not_reachable",
    LineStatus.OK: "ok",
}
PARALLEL_UPDATES = 0
SENSOR_TYPES: Final[dict[str, SensorEntityDescription]] = {
    SensorType.AIR_HUMIDITY: SensorEntityDescription(
        key="air_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
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
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
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
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lunatone sensors from the config entry."""
    coordinator_info = config_entry.runtime_data.coordinator_info
    coordinator_sensors = config_entry.runtime_data.coordinator_sensors

    assert config_entry.unique_id is not None

    entities: list[SensorEntity] = [
        LunatoneSensor(
            coordinator_sensors, description, sensor_id, config_entry.unique_id
        )
        for sensor_id, sensor_data in coordinator_sensors.data.items()
        if (description := SENSOR_TYPES.get(sensor_data.data.type))
    ]
    entities.extend(
        LunatoneDALILineStatusSensor(coordinator_info, line_id, config_entry.unique_id)
        for line_id in coordinator_info.data.lines
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

        self._attr_name = self.sensor.data.name
        self._attr_unique_id = (
            f"{config_entry_unique_id}-sensor{sensor_id}-{description.key}"
        )
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._config_entry_unique_id)},
        )
        if (
            self.sensor.data.address_type == SensorAddressType.DALI
            and self.sensor.data.dali_sensor_address
        ):
            device_info = DeviceInfo(
                identifiers={
                    (
                        DOMAIN,
                        f"{self._config_entry_unique_id}"
                        f"-line{self.sensor.data.dali_sensor_address.line}"
                        f"-d24-address{self.sensor.data.dali_sensor_address.address}",
                    )
                },
                name=(
                    f"DALI Line {self.sensor.data.dali_sensor_address.line}"
                    f" - A{self.sensor.data.dali_sensor_address.address}\u00b2"
                ),
                via_device_id=dr.async_get_device_id_by_identifier(
                    self.coordinator.hass,
                    (DOMAIN, str(self._config_entry_unique_id)),
                    config_entry_id=self.coordinator.config_entry.entry_id,
                ),
            )
        self._attr_device_info = device_info

    @property
    def sensor(self) -> Sensor:
        """Return the sensor data."""
        return self.coordinator.data[self._sensor_id]

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._sensor_id in self.coordinator.data

    @property
    @override
    def native_value(self) -> float | None:
        """Return the measurement value of the sensor."""
        return self.sensor.data.value


class LunatoneDALILineStatusSensor(
    CoordinatorEntity[LunatoneInfoDataUpdateCoordinator], SensorEntity
):
    """Representation of a Lunatone DALI line status sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_options = list(DALI_LINE_STATUS_SENSOR_MAPPING.values())
    _attr_state_class = None
    _attr_translation_key = "dali_line_status"

    def __init__(
        self,
        coordinator: LunatoneInfoDataUpdateCoordinator,
        line_id: str,
        config_entry_unique_id: str,
    ) -> None:
        """Initialize a Lunatone DALI line status sensor."""
        super().__init__(coordinator)

        self._config_entry_unique_id = config_entry_unique_id
        self._line_id = line_id

        line_unique_id = f"{config_entry_unique_id}-line{line_id}"
        # Name must match the light platform, either of them may create the device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, line_unique_id)},
            name=f"DALI Line {line_id}",
        )
        self._attr_unique_id = f"{line_unique_id}-status"

    @property
    @override
    def native_value(self) -> str:
        """Return the value of the sensor."""
        return DALI_LINE_STATUS_SENSOR_MAPPING[
            self.coordinator.data.lines[self._line_id].line_status
        ]
