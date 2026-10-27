"""Support for climate."""

from typing import Any, override

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DOMAIN
from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator, alexa_api_call
from .entity import AmazonEntity

PARALLEL_UPDATES = 1

THERMOSTAT_DESCRIPTION = ClimateEntityDescription(key="thermostat", name=None)

AMAZON_TO_HVAC_MODE = {
    "AUTO": HVACMode.HEAT_COOL,
    "COOL": HVACMode.COOL,
    # ECO keeps a heat/cool range, so it is shown as heat/cool
    "ECO": HVACMode.HEAT_COOL,
    "HEAT": HVACMode.HEAT,
    "OFF": HVACMode.OFF,
}
HVAC_MODE_TO_AMAZON = {
    HVACMode.COOL: "COOL",
    HVACMode.HEAT: "HEAT",
    HVACMode.HEAT_COOL: "AUTO",
    HVACMode.OFF: "OFF",
}

AMAZON_TO_UNIT = {
    "CELSIUS": UnitOfTemperature.CELSIUS,
    "FAHRENHEIT": UnitOfTemperature.FAHRENHEIT,
}
UNIT_TO_AMAZON: dict[str, str] = {value: key for key, value in AMAZON_TO_UNIT.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices climate based on a config entry."""

    coordinator = entry.runtime_data

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        known_devices.intersection_update(current_devices)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                AmazonClimateEntity(coordinator, serial_num, THERMOSTAT_DESCRIPTION)
                for serial_num in new_devices
                if "thermostat" in coordinator.data[serial_num].features
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


def _format_temperature(value: float) -> str:
    """Format a temperature the way Amazon expects it."""
    if float(value).is_integer():
        return str(int(value))
    return str(value)


class AmazonClimateEntity(AmazonEntity, ClimateEntity):
    """Thermostat device."""

    _attr_target_temperature_step = 1

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        serial_num: str,
        description: ClimateEntityDescription,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator, serial_num, description)
        self._attr_hvac_modes = list(
            dict.fromkeys(
                AMAZON_TO_HVAC_MODE[mode]
                for mode in self.device.features["thermostat"][""].supported_modes
                if mode in AMAZON_TO_HVAC_MODE
            )
        )
        self._power_features = ClimateEntityFeature(0)
        if HVACMode.OFF in self._attr_hvac_modes and len(self._attr_hvac_modes) > 1:
            self._power_features = (
                ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
            )

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return the supported features for the current mode."""
        # a single target in heat/cool mode would not be applied by the thermostat
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._power_features | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        return self._power_features | ClimateEntityFeature.TARGET_TEMPERATURE

    def _sensor(self, feature_name: str, property_name: str) -> Any:
        """Return the sensor of a feature property, None if unknown."""
        if (
            (feature := self.device.features.get(feature_name, {}).get("")) is None
            or (sensor_key := feature.sensor_keys.get(property_name)) is None
            or (sensor := self.coordinator.device_sensor(self._serial_num, sensor_key))
            is None
            or sensor.error
        ):
            return None
        return sensor

    def _sensor_value(self, feature_name: str, property_name: str) -> Any:
        """Return the current value of a feature property, None if unknown."""
        if (sensor := self._sensor(feature_name, property_name)) is None:
            return None
        return sensor.value

    def _setpoint(self, property_name: str) -> float | None:
        """Return a thermostat setpoint, None if unknown."""
        if (value := self._sensor_value("thermostat", property_name)) is None:
            return None
        return float(value)

    def _allowed_range(self, operation: str) -> tuple[float, float] | None:
        """Return the allowed heating or cooling range, None if unknown."""
        if (
            allowed := self._sensor_value(
                "thermostatConfiguration", "allowedTemperatureRange"
            )
        ) is None or (allowed_range := allowed.get(operation)) is None:
            return None
        return (
            self._to_native(allowed_range["minimum"]),
            self._to_native(allowed_range["maximum"]),
        )

    def _to_native(self, temperature: dict[str, Any]) -> float:
        """Convert an Amazon temperature to the thermostat unit."""
        return TemperatureConverter.convert(
            float(temperature["value"]),
            AMAZON_TO_UNIT[temperature["scale"]],
            self.native_temperature_unit,
        )

    @property
    @override
    def native_temperature_unit(self) -> str:
        """Return the unit of measurement used by the thermostat."""
        for feature_name, property_name in (
            ("thermostat", "targetSetpoint"),
            ("thermostat", "lowerSetpoint"),
            ("thermostat", "upperSetpoint"),
            ("temperatureSensor", "temperature"),
        ):
            if (sensor := self._sensor(feature_name, property_name)) is not None:
                return AMAZON_TO_UNIT.get(sensor.scale, UnitOfTemperature.FAHRENHEIT)
        return UnitOfTemperature.FAHRENHEIT

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        if (mode := self._sensor_value("thermostat", "thermostatMode")) is None:
            return None
        return AMAZON_TO_HVAC_MODE.get(mode)

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        if (value := self._sensor_value("temperatureSensor", "temperature")) is None:
            return None
        return float(value)

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the target temperature."""
        if self.hvac_mode not in (HVACMode.HEAT, HVACMode.COOL):
            return None
        return self._setpoint("targetSetpoint")

    @property
    @override
    def native_target_temperature_low(self) -> float | None:
        """Return the lower bound of the target temperature range."""
        return self._setpoint("lowerSetpoint")

    @property
    @override
    def native_target_temperature_high(self) -> float | None:
        """Return the upper bound of the target temperature range."""
        return self._setpoint("upperSetpoint")

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum settable temperature."""
        operation = "cooling" if self.hvac_mode == HVACMode.COOL else "heating"
        if (allowed_range := self._allowed_range(operation)) is None:
            return super().min_temp
        return allowed_range[0]

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum settable temperature."""
        operation = "heating" if self.hvac_mode == HVACMode.HEAT else "cooling"
        if (allowed_range := self._allowed_range(operation)) is None:
            return super().max_temp
        return allowed_range[1]

    async def _call(
        self,
        operation_name: str,
        command_payload: dict[str, Any],
        new_values: dict[str, Any],
    ) -> None:
        """Invoke a thermostat feature operation and store the new values."""
        async with alexa_api_call(self.coordinator):
            await self.coordinator.api.call_feature_operation(
                self.device,
                "thermostat",
                operation_name,
                command_payload=command_payload,
            )
        # Optimistic until Amazon pushes or a poll returns the new state
        for property_name, value in new_values.items():
            if (sensor := self._sensor("thermostat", property_name)) is not None:
                sensor.value = value
        self.async_write_ha_state()

    def _temperature_payload(self, value: float) -> dict[str, str]:
        """Return a setpoint payload in the thermostat scale."""
        return {
            "value": _format_temperature(value),
            "scale": UNIT_TO_AMAZON[self.native_temperature_unit],
        }

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        mode = HVAC_MODE_TO_AMAZON[hvac_mode]
        await self._call(
            "setThermostatMode", {"thermostatMode": mode}, {"thermostatMode": mode}
        )

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature or temperature range."""
        # the available setpoints depend on the mode, so both cannot change at once
        if ATTR_HVAC_MODE in kwargs:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="hvac_mode_with_temperature",
            )
        if ATTR_TEMPERATURE in kwargs:
            target = kwargs[ATTR_TEMPERATURE]
            await self._call(
                "setTargetSetpoint",
                {"targetSetpoint": self._temperature_payload(target)},
                {"targetSetpoint": target},
            )
        if ATTR_TARGET_TEMP_LOW in kwargs and ATTR_TARGET_TEMP_HIGH in kwargs:
            low = kwargs[ATTR_TARGET_TEMP_LOW]
            high = kwargs[ATTR_TARGET_TEMP_HIGH]
            await self._call(
                "setTargetSetpoint",
                {
                    "lowerSetpoint": self._temperature_payload(low),
                    "upperSetpoint": self._temperature_payload(high),
                },
                {"lowerSetpoint": low, "upperSetpoint": high},
            )
