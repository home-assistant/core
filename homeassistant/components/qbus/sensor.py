"""Support for Qbus sensor."""

from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import (
    GaugeKey,
    QbusMqttGaugeState,
    QbusMqttThermoState,
    QbusMqttVentilationState,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONCENTRATION_PARTS_PER_MILLION, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import QbusConfigEntry
from .entity import QbusEntity, add_new_outputs

PARALLEL_UPDATES = 0

_SUPPORTED_GAUGE_VARIANTS = {
    "AIRQUALITY": SensorDeviceClass.CO2,
    "CURRENT": SensorDeviceClass.CURRENT,
    "ENERGY": SensorDeviceClass.ENERGY,
    "POWER": SensorDeviceClass.POWER,
    "TEMPERATURE": SensorDeviceClass.TEMPERATURE,
    "VOLTAGE": SensorDeviceClass.VOLTAGE,
    "VOLUME": SensorDeviceClass.VOLUME_STORAGE,
    "WATER": SensorDeviceClass.WATER,
}
_SUPPORTED_GAUGE_PROPERTIES = [
    "consumptionValue",
    "currentValue",
]


def _is_gauge_with_variant(output: QbusMqttOutput) -> bool:
    return (
        output.type == "gauge"
        and isinstance(output.variant, str)
        and _SUPPORTED_GAUGE_VARIANTS.get(output.variant.upper()) is not None
    )


def _is_gauge_with_properties(output: QbusMqttOutput) -> bool:
    return output.type == "gauge" and any(
        supported in output.properties for supported in _SUPPORTED_GAUGE_PROPERTIES
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

    def _check_outputs() -> None:
        entities: list[QbusEntity] = []

        _check_thermo_outputs(entities)
        _check_gauge_variant_outputs(entities)
        # _check_gauge_property_outputs(entities)
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

        variant = (
            _SUPPORTED_GAUGE_VARIANTS.get(mqtt_output.variant.upper(), None)
            if isinstance(mqtt_output.variant, str)
            else None
        )
        current_value_property: dict = mqtt_output.properties.get("currentValue", {})
        unit = current_value_property.get("unit")

        if (variant in ("water", "volume_storage")) and unit == "l":
            unit = unit.upper()

        self._attr_name = mqtt_output.name.title()
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = variant
        self._attr_state_class = "total" if unit in ("kWh", "L") else "measurement"

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
