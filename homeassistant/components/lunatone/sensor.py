"""Platform for Lunatone sensor integration."""

from collections.abc import Callable
import contextlib
from functools import partial
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
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
        translation_key="air_humidity",
    ),
    SensorType.AIR_PRESSURE: SensorEntityDescription(
        key="air_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="air_pressure",
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
        translation_key="eco2",
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
SPECIAL_SENSOR_TYPES: Final[dict[tuple[str, SensorType], SensorEntityDescription]] = {
    ("CPU temperature", SensorType.TEMPERATURE): SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="cpu_temperature",
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LunatoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lunatone sensors from the config entry."""
    coordinator_info = config_entry.runtime_data.coordinator_info
    coordinator_sensors = config_entry.runtime_data.coordinator_sensors

    config_entry_unique_id = config_entry.unique_id
    assert config_entry_unique_id is not None

    def _add_entities(
        entity_builder: dict[str, Callable[[], SensorEntity]], known_entities: set[str]
    ) -> None:
        current_entities = entity_builder.keys()
        new_entities = current_entities - known_entities
        stale_entities = known_entities - current_entities

        if new_entities:
            async_add_entities(
                [
                    entity_builder[entity_unique_id]()
                    for entity_unique_id in new_entities
                ]
            )
            known_entities.update(new_entities)
        known_entities.difference_update(stale_entities)

    known_line_status_entities: set[str] = set()

    @callback
    def _check_line_status_entities() -> None:
        entity_builder: dict[str, Callable[[], SensorEntity]] = {}
        for line_id in map(int, coordinator_info.data.lines):
            unique_id = LunatoneDALILineStatusSensor.construct_unique_id(
                config_entry_unique_id, line_id
            )
            entity_builder[unique_id] = partial(
                LunatoneDALILineStatusSensor,
                coordinator_info,
                line_id,
                config_entry_unique_id,
            )
        _add_entities(entity_builder, known_line_status_entities)

    _check_line_status_entities()
    config_entry.async_on_unload(
        coordinator_info.async_add_listener(_check_line_status_entities)
    )

    if coordinator_sensors is not None:
        known_sensor_entities: set[str] = set()

        @callback
        def _check_sensor_entities() -> None:
            entity_builder: dict[str, Callable[[], SensorEntity]] = {}
            for sensor_id, sensor in coordinator_sensors.data.items():
                if description := (
                    SPECIAL_SENSOR_TYPES.get((sensor.data.name, sensor.data.type))
                    or SENSOR_TYPES.get(sensor.data.type)
                ):
                    unique_id = LunatoneSensor.construct_unique_id(
                        config_entry_unique_id, sensor_id, description.key
                    )
                    entity_builder[unique_id] = partial(
                        LunatoneSensor,
                        coordinator_sensors,
                        coordinator_info,
                        description,
                        sensor_id,
                        config_entry_unique_id,
                    )
            _add_entities(entity_builder, known_sensor_entities)

        _check_sensor_entities()
        config_entry.async_on_unload(
            coordinator_sensors.async_add_listener(_check_sensor_entities)
        )


class LunatoneSensor(
    CoordinatorEntity[LunatoneSensorsDataUpdateCoordinator], SensorEntity
):
    """Representation of a Lunatone Sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator_sensors: LunatoneSensorsDataUpdateCoordinator,
        coordinator_info: LunatoneInfoDataUpdateCoordinator,
        description: SensorEntityDescription,
        sensor_id: int,
        config_entry_unique_id: str,
    ) -> None:
        """Initialize a Lunatone Sensor."""
        super().__init__(coordinator_sensors)
        self.entity_description = description

        self._coordinator_info = coordinator_info
        self._sensor_id = sensor_id
        self._line_id: int | None = None

        self._attr_unique_id = self.construct_unique_id(
            config_entry_unique_id, sensor_id, description.key
        )
        device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, config_entry_unique_id)},
        )
        if (
            self.sensor.data.address_type == SensorAddressType.DALI
            and self.sensor.data.dali_sensor_address
        ):
            self._line_id = self.sensor.data.dali_sensor_address.line
            linked_device_unique_id = f"{config_entry_unique_id}-line{self._line_id}"
            device_info = dr.DeviceInfo(
                identifiers={
                    (
                        DOMAIN,
                        (
                            f"{linked_device_unique_id}"
                            f"-d24-address{self.sensor.data.dali_sensor_address.address}"
                        ),
                    )
                },
                translation_key="dali_sensor",
                translation_placeholders={
                    "line_id": str(self._line_id),
                    "dali_address": str(self.sensor.data.dali_sensor_address.address),
                },
            )
            with contextlib.suppress(ValueError):
                device_info.via_device_id = dr.async_get_device_id_by_identifier(
                    self.coordinator.hass,
                    (DOMAIN, f"{linked_device_unique_id}"),
                    config_entry_id=self.coordinator.config_entry.entry_id,
                )
        self._attr_device_info = device_info

    @staticmethod
    def construct_unique_id(
        config_entry_unique_id: str, sensor_id: int, key: str
    ) -> str:
        """Returns the unique_id for a device ID."""
        return f"{config_entry_unique_id}-sensor{sensor_id}-{key}"

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        if self._line_id is not None:
            self.async_on_remove(
                self._coordinator_info.async_add_listener(self._handle_info_update)
            )

    @callback
    def _handle_info_update(self) -> None:
        assert self._line_id is not None

        config_entry_id = self.coordinator.config_entry.entry_id
        device_registry = dr.async_get(self.hass)
        linked_device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{self.coordinator.config_entry.unique_id}-line{self._line_id}"),
            config_entry_id,
        )

        if (
            linked_device
            and self.registry_entry
            and self.registry_entry.device_id is not None
        ):
            device = device_registry.async_get(
                self.registry_entry.device_id, include_child_devices=False
            )
            if device and device.via_device_id != linked_device.id:
                device_registry.async_update_device(
                    device.id, via_device_id=linked_device.id
                )

        self.async_write_ha_state()

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
        line_id: int,
        config_entry_unique_id: str,
    ) -> None:
        """Initialize a Lunatone DALI line status sensor."""
        super().__init__(coordinator)

        self._config_entry_unique_id = config_entry_unique_id
        self._line_id = line_id

        # Name must match the light platform, either of them may create the device
        self._attr_device_info = dr.DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.construct_device_unique_id(config_entry_unique_id, line_id),
                )
            },
            translation_key="dali_line",
            translation_placeholders={"line_id": str(line_id)},
        )
        self._attr_unique_id = self.construct_unique_id(config_entry_unique_id, line_id)

    @staticmethod
    def construct_device_unique_id(
        config_entry_unique_id: str, line_id: int | None = None
    ) -> str:
        """Returns the unique_id of the parent device."""
        return f"{config_entry_unique_id}-line{line_id}"

    @staticmethod
    def construct_unique_id(
        config_entry_unique_id: str, line_id: int | None = None
    ) -> str:
        """Returns the unique_id for a device ID."""
        return f"{config_entry_unique_id}-line{line_id}-status"

    @property
    @override
    def available(self) -> bool:
        return super().available and str(self._line_id) in self.coordinator.data.lines

    @property
    @override
    def native_value(self) -> str:
        """Return the value of the sensor."""
        line_data = self.coordinator.data.lines.get(str(self._line_id))
        return (
            DALI_LINE_STATUS_SENSOR_MAPPING[line_data.line_status]
            if line_data is not None
            else "not_reachable"
        )
