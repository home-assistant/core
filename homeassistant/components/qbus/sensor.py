"""Support for Qbus sensor."""

from dataclasses import dataclass

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import (
    GaugeKey,
    QbusMqttGaugeState,
    QbusMqttHumidityState,
    QbusMqttThermoState,
    QbusMqttVentilationState,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
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
from .entity import QbusEntity, add_new_outputs

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class Description:
    """Custom description for sensors."""

    device_class: SensorDeviceClass | None = None
    unit: str | None = None
    state_class: SensorStateClass | str | None = None


_GAUGE_VARIANT_DESCRIPTIONS = {
    "AIRPRESSURE": Description(
        device_class=SensorDeviceClass.PRESSURE,
        unit=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "AIRQUALITY": Description(
        device_class=SensorDeviceClass.CO2,
        unit=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CURRENT": Description(
        device_class=SensorDeviceClass.CURRENT,
        unit=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ENERGY": Description(
        device_class=SensorDeviceClass.ENERGY,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    "GAS": Description(
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        unit=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "GASFLOW": Description(
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        unit=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "HUMIDITY": Description(
        device_class=SensorDeviceClass.HUMIDITY,
        unit=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LIGHT": Description(
        device_class=SensorDeviceClass.ILLUMINANCE,
        unit=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "LOUDNESS": Description(
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        unit=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "POWER": Description(
        device_class=SensorDeviceClass.POWER,
        unit=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "PRESSURE": Description(
        device_class=SensorDeviceClass.PRESSURE,
        unit=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "TEMPERATURE": Description(
        device_class=SensorDeviceClass.TEMPERATURE,
        unit=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VOLTAGE": Description(
        device_class=SensorDeviceClass.VOLTAGE,
        unit=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VOLUME": Description(
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        unit=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WATER": Description(
        device_class=SensorDeviceClass.WATER,
        unit=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
    ),
    "WATERFLOW": Description(
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        unit=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WATERLEVEL": Description(
        device_class=SensorDeviceClass.DISTANCE,
        unit=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WATERPRESSURE": Description(
        device_class=SensorDeviceClass.PRESSURE,
        unit=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "WIND": Description(
        device_class=SensorDeviceClass.WIND_SPEED,
        unit=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}
_SUPPORTED_GAUGE_PROPERTIES = [
    "consumptionValue",
    "currentValue",
]


def _is_gauge_with_variant(output: QbusMqttOutput) -> bool:
    return (
        output.type == "gauge"
        and isinstance(output.variant, str)
        and _GAUGE_VARIANT_DESCRIPTIONS.get(output.variant.upper()) is not None
    )


def _is_gauge_with_properties(output: QbusMqttOutput) -> bool:
    return (
        output.type == "gauge"
        and not isinstance(output.variant, str)
        and any(
            supported in output.properties for supported in _SUPPORTED_GAUGE_PROPERTIES
        )
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

    def _check_thermo_outputs(entities: list[QbusEntity]) -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            lambda output: output.type == "thermo",
            QbusThermoSensor,
            entities,
        )

    def _check_gauge_variant_outputs(entities: list[QbusEntity]) -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            _is_gauge_with_variant,
            QbusGaugeVariantSensor,
            entities,
        )

    def _check_gauge_property_outputs(entities: list[QbusEntity]) -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            _is_gauge_with_properties,
            QbusGaugePropertySensor,
            entities,
        )

    def _check_ventilation_outputs(entities: list[QbusEntity]) -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            _is_ventilation_with_co2,
            QbusVentilationSensor,
            entities,
        )

    # def _check_weather_outputs(entities: list[QbusEntity]) -> None:
    #     add_new_outputs(
    #         coordinator,
    #         added_outputs,
    #         lambda output: output.type == "weatherstation",
    #         QbusThermoSensor,
    #         entities,
    #     )

    def _check_humidity_outputs(entities: list[QbusEntity]) -> None:
        add_new_outputs(
            coordinator,
            added_outputs,
            lambda output: output.type == "humidity",
            QbusHumiditySensor,
            entities,
        )

    def _check_outputs() -> None:
        entities: list[QbusEntity] = []

        # _check_gauge_property_outputs(entities)
        _check_gauge_variant_outputs(entities)
        _check_humidity_outputs(entities)
        _check_thermo_outputs(entities)
        _check_ventilation_outputs(entities)

        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_check_outputs))


class QbusThermoSensor(QbusEntity, SensorEntity):
    """Representation of a Qbus sensor entity for thermostats."""

    _state_cls = QbusMqttThermoState

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_name = None
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    async def _handle_state_received(self, state: QbusMqttThermoState) -> None:
        self._attr_native_value = state.read_current_temperature()


class QbusGaugeVariantSensor(QbusEntity, SensorEntity):
    """Representation of a Qbus sensor entity for gauges with variant."""

    _state_cls = QbusMqttGaugeState

    _attr_suggested_display_precision = 2

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize sensor entity."""

        super().__init__(mqtt_output, link_to_main_device=True)

        variant = str(mqtt_output.variant)
        description = _GAUGE_VARIANT_DESCRIPTIONS[variant.upper()]

        self._attr_device_class = description.device_class
        self._attr_name = mqtt_output.name.title()
        self._attr_native_unit_of_measurement = description.unit
        self._attr_state_class = description.state_class

    async def _handle_state_received(self, state: QbusMqttGaugeState) -> None:
        self._attr_native_value = state.read_value(GaugeKey.CURRENT_VALUE)


class QbusGaugePropertySensor(QbusEntity, SensorEntity):
    """Representation of a Qbus sensor entity for gauges with properties."""

    _state_cls = QbusMqttGaugeState

    _attr_suggested_display_precision = 2

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize sensor entity."""

        super().__init__(mqtt_output, link_to_main_device=True)

        current_value_property: dict = mqtt_output.properties.get("currentValue", {})
        unit = current_value_property.get("unit")

        self._attr_name = mqtt_output.name.title()
        self._attr_native_unit_of_measurement = unit

        match unit:
            case "kWh":
                self._attr_device_class = SensorDeviceClass.ENERGY
                self._attr_state_class = SensorStateClass.TOTAL
            case "L":
                self._attr_device_class = SensorDeviceClass.VOLUME_STORAGE
                self._attr_state_class = SensorStateClass.TOTAL
            case _:
                self._attr_state_class = SensorStateClass.MEASUREMENT

    async def _handle_state_received(self, state: QbusMqttGaugeState) -> None:
        self._attr_native_value = state.read_value(GaugeKey.CURRENT_VALUE)


class QbusVentilationSensor(QbusEntity, SensorEntity):
    """Representation of a Qbus sensor entity for ventilations."""

    _state_cls = QbusMqttVentilationState

    _attr_device_class = SensorDeviceClass.CO2
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize sensor entity."""

        super().__init__(mqtt_output, link_to_main_device=True)

        self._attr_name = mqtt_output.name.title()

    async def _handle_state_received(self, state: QbusMqttVentilationState) -> None:
        self._attr_native_value = state.read_co2()


class QbusHumiditySensor(QbusEntity, SensorEntity):
    """Representation of a Qbus sensor entity for humidity modules."""

    _state_cls = QbusMqttHumidityState

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, mqtt_output: QbusMqttOutput) -> None:
        """Initialize sensor entity."""

        super().__init__(mqtt_output, link_to_main_device=True)

        self._attr_name = mqtt_output.name.title()

    async def _handle_state_received(self, state: QbusMqttHumidityState) -> None:
        self._attr_native_value = state.read_value()
