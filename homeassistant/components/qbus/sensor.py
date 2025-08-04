"""Support for Qbus sensor."""

from dataclasses import dataclass

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import (
    GaugeStateProperty,
    QbusMqttGaugeState,
    QbusMqttHumidityState,
    QbusMqttThermoState,
    QbusMqttVentilationState,
    QbusMqttWeatherState,
)

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
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QbusConfigEntry
from .entity import QbusEntity, create_new_entities, determine_new_outputs

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class QbusWeatherDescription(SensorEntityDescription):
    """Description for Qbus weather entities."""

    property: str


_WEATHER_DESCRIPTIONS = (
    QbusWeatherDescription(
        key="daylight",
        property="dayLight",
        translation_key="daylight",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    QbusWeatherDescription(
        key="light",
        property="light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    QbusWeatherDescription(
        key="light_east",
        property="lightEast",
        translation_key="light_east",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    QbusWeatherDescription(
        key="light_south",
        property="lightSouth",
        translation_key="light_south",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    QbusWeatherDescription(
        key="light_west",
        property="lightWest",
        translation_key="light_west",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
    ),
    QbusWeatherDescription(
        key="temperature",
        property="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    QbusWeatherDescription(
        key="wind",
        property="wind",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
    ),
)

_GAUGE_VARIANT_DESCRIPTIONS = {
    "AIRPRESSURE": SensorEntityDescription(
        key="airpressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "AIRQUALITY": SensorEntityDescription(
        key="airquality",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT": SensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ENERGY": SensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    "GAS": SensorEntityDescription(
        key="gas",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "GASFLOW": SensorEntityDescription(
        key="gasflow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "HUMIDITY": SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LIGHT": SensorEntityDescription(
        key="light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LOUDNESS": SensorEntityDescription(
        key="loudness",
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "POWER": SensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "PRESSURE": SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "TEMPERATURE": SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VOLTAGE": SensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VOLUME": SensorEntityDescription(
        key="volume",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WATER": SensorEntityDescription(
        key="water",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
    ),
    "WATERFLOW": SensorEntityDescription(
        key="waterflow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WATERLEVEL": SensorEntityDescription(
        key="waterlevel",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WATERPRESSURE": SensorEntityDescription(
        key="waterpressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WIND": SensorEntityDescription(
        key="wind",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def _is_gauge_with_variant(output: QbusMqttOutput) -> bool:
    return (
        output.type == "gauge"
        and isinstance(output.variant, str)
        and _GAUGE_VARIANT_DESCRIPTIONS.get(output.variant.upper()) is not None
    )


def _is_ventilation_with_co2(output: QbusMqttOutput) -> bool:
    return output.type == "ventilation" and output.properties.get("co2") is not None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: QbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""

    coordinator = entry.runtime_data
    added_outputs: list[QbusMqttOutput] = []

    def _create_weather_entities() -> list[QbusEntity]:
        new_outputs = determine_new_outputs(
            coordinator, added_outputs, lambda output: output.type == "weatherstation"
        )

        return [
            QbusWeatherSensor(output, description)
            for output in new_outputs
            for description in _WEATHER_DESCRIPTIONS
        ]

    def _check_outputs() -> None:
        entities: list[QbusEntity] = [
            *create_new_entities(
                coordinator,
                added_outputs,
                _is_gauge_with_variant,
                QbusGaugeVariantSensor,
            ),
            *create_new_entities(
                coordinator,
                added_outputs,
                lambda output: output.type == "humidity",
                QbusHumiditySensor,
            ),
            *create_new_entities(
                coordinator,
                added_outputs,
                lambda output: output.type == "thermo",
                QbusThermoSensor,
            ),
            *create_new_entities(
                coordinator,
                added_outputs,
                _is_ventilation_with_co2,
                QbusVentilationSensor,
            ),
            *_create_weather_entities(),
        ]

        async_add_entities(entities)

    _check_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusGaugeVariantSensor(QbusEntity, SensorEntity):
    """Representation of a Qbus sensor entity for gauges with variant."""

    _state_cls = QbusMqttGaugeState

    _attr_name = None
    _attr_suggested_display_precision = 2

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize sensor entity."""

        super().__init__(mqtt_output)

        variant = str(mqtt_output.variant)
        self.entity_description = _GAUGE_VARIANT_DESCRIPTIONS[variant.upper()]

    async def _handle_state_received(self, state: QbusMqttGaugeState) -> None:
        self._attr_native_value = state.read_value(GaugeStateProperty.CURRENT_VALUE)


class QbusHumiditySensor(QbusEntity, SensorEntity):
    """Representation of a Qbus sensor entity for humidity modules."""

    _state_cls = QbusMqttHumidityState

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_name = None
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    async def _handle_state_received(self, state: QbusMqttHumidityState) -> None:
        self._attr_native_value = state.read_value()


class QbusThermoSensor(QbusEntity, SensorEntity):
    """Representation of a Qbus sensor entity for thermostats."""

    _state_cls = QbusMqttThermoState

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    async def _handle_state_received(self, state: QbusMqttThermoState) -> None:
        self._attr_native_value = state.read_current_temperature()


class QbusVentilationSensor(QbusEntity, SensorEntity):
    """Representation of a Qbus sensor entity for ventilations."""

    _state_cls = QbusMqttVentilationState

    _attr_device_class = SensorDeviceClass.CO2
    _attr_name = None
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    async def _handle_state_received(self, state: QbusMqttVentilationState) -> None:
        self._attr_native_value = state.read_co2()


class QbusWeatherSensor(QbusEntity, SensorEntity):
    """Representation of a Qbus weather sensor."""

    _state_cls = QbusMqttWeatherState

    entity_description: QbusWeatherDescription

    def __init__(
        self, mqtt_output: QbusMqttOutput, description: QbusWeatherDescription
    ) -> None:
        """Initialize sensor entity."""

        super().__init__(mqtt_output, id_suffix=description.key)

        self.entity_description = description

        if description.key == "temperature":
            self._attr_name = None

    async def _handle_state_received(self, state: QbusMqttWeatherState) -> None:
        if value := state.read_property(self.entity_description.property, None):
            self.native_value = value
