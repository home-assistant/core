"""Support for HomematicIP Cloud sensors."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homematicip.base.enums import FunctionalChannelType, ValveState
from homematicip.base.functionalChannels import (
    FloorTerminalBlockMechanicChannel,
    FunctionalChannel,
)
from homematicip.device import (
    BrandSwitchMeasuring,
    EnergySensorsInterface,
    FloorTerminalBlock6,
    FloorTerminalBlock10,
    FloorTerminalBlock12,
    FullFlushSwitchMeasuring,
    HeatingThermostat,
    HeatingThermostatCompact,
    HeatingThermostatEvo,
    HomeControlAccessPoint,
    LightSensor,
    MotionDetectorIndoor,
    MotionDetectorOutdoor,
    MotionDetectorPushButton,
    PassageDetector,
    PlugableSwitchMeasuring,
    PresenceDetectorIndoor,
    RoomControlDeviceAnalog,
    TemperatureDifferenceSensor2,
    TemperatureHumiditySensorDisplay,
    TemperatureHumiditySensorOutdoor,
    TemperatureHumiditySensorWithoutDisplay,
    TiltVibrationSensor,
    WeatherSensor,
    WeatherSensorPlus,
    WeatherSensorPro,
    WiredFloorTerminalBlock12,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .entity import HomematicipGenericEntity
from .hap import HomematicipHAP
from .helpers import get_channels_from_device

ATTR_ACCELERATION_SENSOR_NEUTRAL_POSITION = "acceleration_sensor_neutral_position"
ATTR_ACCELERATION_SENSOR_TRIGGER_ANGLE = "acceleration_sensor_trigger_angle"
ATTR_ACCELERATION_SENSOR_SECOND_TRIGGER_ANGLE = (
    "acceleration_sensor_second_trigger_angle"
)
ATTR_CURRENT_ILLUMINATION = "current_illumination"
ATTR_LOWEST_ILLUMINATION = "lowest_illumination"
ATTR_HIGHEST_ILLUMINATION = "highest_illumination"
ATTR_LEFT_COUNTER = "left_counter"
ATTR_RIGHT_COUNTER = "right_counter"
ATTR_TEMPERATURE_OFFSET = "temperature_offset"
ATTR_WIND_DIRECTION = "wind_direction"
ATTR_WIND_DIRECTION_VARIATION = "wind_direction_variation_in_degree"
ATTR_ESI_TYPE = "type"
ESI_TYPE_UNKNOWN = "UNKNOWN"
ESI_CONNECTED_SENSOR_TYPE_IEC = "ES_IEC"
ESI_CONNECTED_SENSOR_TYPE_GAS = "ES_GAS"
ESI_CONNECTED_SENSOR_TYPE_LED = "ES_LED"

ESI_TYPE_CURRENT_POWER_CONSUMPTION = "CurrentPowerConsumption"
ESI_TYPE_ENERGY_COUNTER_USAGE_HIGH_TARIFF = "ENERGY_COUNTER_USAGE_HIGH_TARIFF"
ESI_TYPE_ENERGY_COUNTER_USAGE_LOW_TARIFF = "ENERGY_COUNTER_USAGE_LOW_TARIFF"
ESI_TYPE_ENERGY_COUNTER_INPUT_SINGLE_TARIFF = "ENERGY_COUNTER_INPUT_SINGLE_TARIFF"
ESI_TYPE_CURRENT_GAS_FLOW = "CurrentGasFlow"
ESI_TYPE_CURRENT_GAS_VOLUME = "GasVolume"

ILLUMINATION_DEVICE_ATTRIBUTES = {
    "currentIllumination": ATTR_CURRENT_ILLUMINATION,
    "lowestIllumination": ATTR_LOWEST_ILLUMINATION,
    "highestIllumination": ATTR_HIGHEST_ILLUMINATION,
}

TILT_STATE_VALUES = ["neutral", "tilted", "non_neutral"]


def get_device_handlers(hap: HomematicipHAP) -> dict[type, Callable]:
    """Generate a mapping of device types to handler functions."""
    return {
        HomeControlAccessPoint: lambda device: [
            HomematicipAccesspointDutyCycle(hap, device)
        ],
        HeatingThermostat: lambda device: [
            HomematicipHeatingThermostat(hap, device),
            HomematicipTemperatureSensor(hap, device),
        ],
        HeatingThermostatCompact: lambda device: [
            HomematicipHeatingThermostat(hap, device),
            HomematicipTemperatureSensor(hap, device),
        ],
        HeatingThermostatEvo: lambda device: [
            HomematicipHeatingThermostat(hap, device),
            HomematicipTemperatureSensor(hap, device),
        ],
        TemperatureHumiditySensorDisplay: lambda device: [
            HomematicipTemperatureSensor(hap, device),
            HomematicipHumiditySensor(hap, device),
            HomematicipAbsoluteHumiditySensor(hap, device),
        ],
        TemperatureHumiditySensorWithoutDisplay: lambda device: [
            HomematicipTemperatureSensor(hap, device),
            HomematicipHumiditySensor(hap, device),
            HomematicipAbsoluteHumiditySensor(hap, device),
        ],
        TemperatureHumiditySensorOutdoor: lambda device: [
            HomematicipTemperatureSensor(hap, device),
            HomematicipHumiditySensor(hap, device),
            HomematicipAbsoluteHumiditySensor(hap, device),
        ],
        RoomControlDeviceAnalog: lambda device: [
            HomematicipTemperatureSensor(hap, device),
        ],
        LightSensor: lambda device: [
            HomematicipIlluminanceSensor(hap, device),
        ],
        MotionDetectorIndoor: lambda device: [
            HomematicipIlluminanceSensor(hap, device),
        ],
        MotionDetectorOutdoor: lambda device: [
            HomematicipIlluminanceSensor(hap, device),
        ],
        MotionDetectorPushButton: lambda device: [
            HomematicipIlluminanceSensor(hap, device),
        ],
        PresenceDetectorIndoor: lambda device: [
            HomematicipIlluminanceSensor(hap, device),
        ],
        PlugableSwitchMeasuring: lambda device: [
            HomematicipPowerSensor(hap, device),
            HomematicipEnergySensor(hap, device),
        ],
        BrandSwitchMeasuring: lambda device: [
            HomematicipPowerSensor(hap, device),
            HomematicipEnergySensor(hap, device),
        ],
        FullFlushSwitchMeasuring: lambda device: [
            HomematicipPowerSensor(hap, device),
            HomematicipEnergySensor(hap, device),
        ],
        PassageDetector: lambda device: [
            HomematicipPassageDetectorDeltaCounter(hap, device),
        ],
        TemperatureDifferenceSensor2: lambda device: [
            HomematicpTemperatureExternalSensorCh1(hap, device),
            HomematicpTemperatureExternalSensorCh2(hap, device),
            HomematicpTemperatureExternalSensorDelta(hap, device),
        ],
        TiltVibrationSensor: lambda device: [
            HomematicipTiltStateSensor(hap, device),
            HomematicipTiltAngleSensor(hap, device),
        ],
        WeatherSensor: lambda device: [
            HomematicipTemperatureSensor(hap, device),
            HomematicipHumiditySensor(hap, device),
            HomematicipIlluminanceSensor(hap, device),
            HomematicipWindspeedSensor(hap, device),
            HomematicipAbsoluteHumiditySensor(hap, device),
        ],
        WeatherSensorPlus: lambda device: [
            HomematicipTemperatureSensor(hap, device),
            HomematicipHumiditySensor(hap, device),
            HomematicipIlluminanceSensor(hap, device),
            HomematicipWindspeedSensor(hap, device),
            HomematicipTodayRainSensor(hap, device),
            HomematicipAbsoluteHumiditySensor(hap, device),
        ],
        WeatherSensorPro: lambda device: [
            HomematicipTemperatureSensor(hap, device),
            HomematicipHumiditySensor(hap, device),
            HomematicipIlluminanceSensor(hap, device),
            HomematicipWindspeedSensor(hap, device),
            HomematicipTodayRainSensor(hap, device),
            HomematicipAbsoluteHumiditySensor(hap, device),
        ],
        EnergySensorsInterface: lambda device: _handle_energy_sensor_interface(
            hap, device
        ),
    }


def _handle_energy_sensor_interface(hap: HomematicipHAP, device) -> list[SensorEntity]:
    """Handle energy sensor interface devices."""
    result: list[SensorEntity] = []
    for ch in get_channels_from_device(
        device, FunctionalChannelType.ENERGY_SENSORS_INTERFACE_CHANNEL
    ):
        if ch.connectedEnergySensorType == ESI_CONNECTED_SENSOR_TYPE_IEC:
            if ch.currentPowerConsumption is not None:
                result.append(HmipEsiIecPowerConsumption(hap, device))
            if ch.energyCounterOneType != ESI_TYPE_UNKNOWN:
                result.append(HmipEsiIecEnergyCounterHighTariff(hap, device))
            if ch.energyCounterTwoType != ESI_TYPE_UNKNOWN:
                result.append(HmipEsiIecEnergyCounterLowTariff(hap, device))
            if ch.energyCounterThreeType != ESI_TYPE_UNKNOWN:
                result.append(HmipEsiIecEnergyCounterInputSingleTariff(hap, device))

        if ch.connectedEnergySensorType == ESI_CONNECTED_SENSOR_TYPE_GAS:
            if ch.currentGasFlow is not None:
                result.append(HmipEsiGasCurrentGasFlow(hap, device))
            if ch.gasVolume is not None:
                result.append(HmipEsiGasGasVolume(hap, device))

        if ch.connectedEnergySensorType == ESI_CONNECTED_SENSOR_TYPE_LED:
            if ch.currentPowerConsumption is not None:
                result.append(HmipEsiLedCurrentPowerConsumption(hap, device))
            result.append(HmipEsiLedEnergyCounterHighTariff(hap, device))

    return result


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP Cloud sensors from a config entry."""
    hap = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[HomematicipGenericEntity] = []

    # Get device handlers dynamically
    device_handlers = get_device_handlers(hap)

    # Process all devices
    for device in hap.home.devices:
        for device_class, handler in device_handlers.items():
            if isinstance(device, device_class):
                entities.extend(handler(device))

    # Handle floor terminal blocks separately
    floor_terminal_blocks = (
        FloorTerminalBlock6,
        FloorTerminalBlock10,
        FloorTerminalBlock12,
        WiredFloorTerminalBlock12,
    )
    entities.extend(
        HomematicipFloorTerminalBlockMechanicChannelValve(
            hap, device, channel=channel.index
        )
        for device in hap.home.devices
        if isinstance(device, floor_terminal_blocks)
        for channel in device.functionalChannels
        if isinstance(channel, FloorTerminalBlockMechanicChannel)
        and getattr(channel, "valvePosition", None) is not None
    )

    async_add_entities(entities)


class HomematicipTiltAngleSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP tilt angle sensor."""

    _attr_native_unit_of_measurement = DEGREE
    _attr_state_class = SensorStateClass.MEASUREMENT_ANGLE

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the tilt angle sensor device."""
        super().__init__(hap, device, post="Tilt Angle")

    @property
    def native_value(self) -> int | None:
        """Return the state."""

        if hasattr(self.functional_channel, "absoluteAngle"):
            return (
                self.functional_channel.absoluteAngle
                if self.functional_channel.absoluteAngle is not None
                else None
            )

        return None


class HomematicipTiltStateSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP tilt sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = TILT_STATE_VALUES
    _attr_translation_key = "tilt_state"

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the tilt sensor device."""
        super().__init__(hap, device, post="Tilt State")

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        if hasattr(self.functional_channel, "tiltState"):
            return (
                self.functional_channel.tiltState.lower()
                if self.functional_channel.tiltState is not None
                else None
            )

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the tilt sensor."""
        state_attr = super().extra_state_attributes

        state_attr[ATTR_ACCELERATION_SENSOR_NEUTRAL_POSITION] = getattr(
            self.functional_channel, "accelerationSensorNeutralPosition", None
        )
        state_attr[ATTR_ACCELERATION_SENSOR_TRIGGER_ANGLE] = getattr(
            self.functional_channel, "accelerationSensorTriggerAngle", None
        )
        state_attr[ATTR_ACCELERATION_SENSOR_SECOND_TRIGGER_ANGLE] = getattr(
            self.functional_channel, "accelerationSensorSecondTriggerAngle", None
        )

        return state_attr


class HomematicipFloorTerminalBlockMechanicChannelValve(
    HomematicipGenericEntity, SensorEntity
):
    """Representation of the HomematicIP floor terminal block."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, hap: HomematicipHAP, device, channel, is_multi_channel=True
    ) -> None:
        """Initialize floor terminal block 12 device."""
        super().__init__(
            hap,
            device,
            channel=channel,
            is_multi_channel=is_multi_channel,
            post="Valve Position",
        )

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        if super().icon:
            return super().icon
        channel = next(
            channel
            for channel in self._device.functionalChannels
            if channel.index == self._channel
        )
        if channel.valveState != ValveState.ADAPTION_DONE:
            return "mdi:alert"
        return "mdi:heating-coil"

    @property
    def native_value(self) -> int | None:
        """Return the state of the floor terminal block mechanical channel valve position."""
        channel = next(
            channel
            for channel in self._device.functionalChannels
            if channel.index == self._channel
        )
        if channel.valveState != ValveState.ADAPTION_DONE:
            return None
        return round(channel.valvePosition * 100)


class HomematicipAccesspointDutyCycle(HomematicipGenericEntity, SensorEntity):
    """Representation of then HomeMaticIP access point."""

    _attr_icon = "mdi:access-point-network"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize access point status entity."""
        super().__init__(hap, device, post="Duty Cycle")

    @property
    def native_value(self) -> float:
        """Return the state of the access point."""
        return self._device.dutyCycleLevel


class HomematicipHeatingThermostat(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP heating thermostat."""

    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize heating thermostat device."""
        super().__init__(hap, device, post="Heating")

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        if super().icon:
            return super().icon
        if self._device.valveState != ValveState.ADAPTION_DONE:
            return "mdi:alert"
        return "mdi:radiator"

    @property
    def native_value(self) -> int | None:
        """Return the state of the radiator valve."""
        if self._device.valveState != ValveState.ADAPTION_DONE:
            return None
        return round(self._device.valvePosition * 100)


class HomematicipHumiditySensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP humidity sensor."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the thermometer device."""
        super().__init__(hap, device, post="Humidity")

    @property
    def native_value(self) -> int:
        """Return the state."""
        return self._device.humidity


class HomematicipTemperatureSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP thermometer."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the thermometer device."""
        super().__init__(hap, device, post="Temperature")

    @property
    def native_value(self) -> float:
        """Return the state."""
        if hasattr(self._device, "valveActualTemperature"):
            return self._device.valveActualTemperature

        return self._device.actualTemperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the windspeed sensor."""
        state_attr = super().extra_state_attributes

        temperature_offset = getattr(self._device, "temperatureOffset", None)
        if temperature_offset:
            state_attr[ATTR_TEMPERATURE_OFFSET] = temperature_offset

        return state_attr


class HomematicipAbsoluteHumiditySensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP absolute humidity sensor."""

    _attr_native_unit_of_measurement = CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the thermometer device."""
        super().__init__(hap, device, post="Absolute Humidity")

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        if self.functional_channel is None:
            return None

        value = self.functional_channel.vaporAmount

        # Handle case where value might be None
        if (
            self.functional_channel.vaporAmount is None
            or self.functional_channel.vaporAmount == ""
        ):
            return None

        # Convert from g/m³ to mg/m³
        return int(float(value) * 1000)


class HomematicipIlluminanceSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP Illuminance sensor."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_native_unit_of_measurement = LIGHT_LUX
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the  device."""
        super().__init__(hap, device, post="Illuminance")

    @property
    def native_value(self) -> float:
        """Return the state."""
        if hasattr(self._device, "averageIllumination"):
            return self._device.averageIllumination

        return self._device.illumination

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the wind speed sensor."""
        state_attr = super().extra_state_attributes

        for attr, attr_key in ILLUMINATION_DEVICE_ATTRIBUTES.items():
            if attr_value := getattr(self._device, attr, None):
                state_attr[attr_key] = attr_value

        return state_attr


class HomematicipPowerSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP power measuring sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the  device."""
        super().__init__(hap, device, post="Power")

    @property
    def native_value(self) -> float:
        """Return the power consumption value."""
        return self._device.currentPowerConsumption


class HomematicipEnergySensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP energy measuring sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the device."""
        super().__init__(hap, device, post="Energy")

    @property
    def native_value(self) -> float:
        """Return the energy counter value."""
        return self._device.energyCounter


class HomematicipWindspeedSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP wind speed sensor."""

    _attr_device_class = SensorDeviceClass.WIND_SPEED
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the windspeed sensor."""
        super().__init__(hap, device, post="Windspeed")

    @property
    def native_value(self) -> float:
        """Return the wind speed value."""
        return self._device.windSpeed

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the wind speed sensor."""
        state_attr = super().extra_state_attributes

        wind_direction = getattr(self._device, "windDirection", None)
        if wind_direction is not None:
            state_attr[ATTR_WIND_DIRECTION] = _get_wind_direction(wind_direction)

        wind_direction_variation = getattr(self._device, "windDirectionVariation", None)
        if wind_direction_variation:
            state_attr[ATTR_WIND_DIRECTION_VARIATION] = wind_direction_variation

        return state_attr


class HomematicipTodayRainSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP rain counter of a day sensor."""

    _attr_device_class = SensorDeviceClass.PRECIPITATION
    _attr_native_unit_of_measurement = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the  device."""
        super().__init__(hap, device, post="Today Rain")

    @property
    def native_value(self) -> float:
        """Return the today's rain value."""
        return round(self._device.todayRainCounter, 2)


class HomematicpTemperatureExternalSensorCh1(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP device HmIP-STE2-PCB."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the  device."""
        super().__init__(hap, device, post="Channel 1 Temperature")

    @property
    def native_value(self) -> float:
        """Return the state."""
        return self._device.temperatureExternalOne


class HomematicpTemperatureExternalSensorCh2(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP device HmIP-STE2-PCB."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the  device."""
        super().__init__(hap, device, post="Channel 2 Temperature")

    @property
    def native_value(self) -> float:
        """Return the state."""
        return self._device.temperatureExternalTwo


class HomematicpTemperatureExternalSensorDelta(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP device HmIP-STE2-PCB."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the  device."""
        super().__init__(hap, device, post="Delta Temperature")

    @property
    def native_value(self) -> float:
        """Return the state."""
        return self._device.temperatureExternalDelta


class HmipEsiSensorEntity(HomematicipGenericEntity, SensorEntity):
    """EntityDescription for HmIP-ESI Sensors."""

    def __init__(
        self,
        hap: HomematicipHAP,
        device: HomematicipGenericEntity,
        key: str,
        value_fn: Callable[[FunctionalChannel], StateType],
        type_fn: Callable[[FunctionalChannel], str],
    ) -> None:
        """Initialize Sensor Entity."""
        super().__init__(
            hap=hap,
            device=device,
            channel=1,
            post=key,
            is_multi_channel=False,
        )

        self._value_fn = value_fn
        self._type_fn = type_fn

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the esi sensor."""
        state_attr = super().extra_state_attributes
        state_attr[ATTR_ESI_TYPE] = self._type_fn(self.functional_channel)

        return state_attr

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return str(self._value_fn(self.functional_channel))


class HmipEsiIecPowerConsumption(HmipEsiSensorEntity):
    """Representation of the Hmip-ESI IEC currentPowerConsumption sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the  device."""
        super().__init__(
            hap,
            device,
            key="CurrentPowerConsumption",
            value_fn=lambda channel: channel.currentPowerConsumption,
            type_fn=lambda channel: "CurrentPowerConsumption",
        )


class HmipEsiIecEnergyCounterHighTariff(HmipEsiSensorEntity):
    """Representation of the Hmip-ESI IEC energyCounterOne sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the  device."""
        super().__init__(
            hap,
            device,
            key=ESI_TYPE_ENERGY_COUNTER_USAGE_HIGH_TARIFF,
            value_fn=lambda channel: channel.energyCounterOne,
            type_fn=lambda channel: channel.energyCounterOneType,
        )


class HmipEsiIecEnergyCounterLowTariff(HmipEsiSensorEntity):
    """Representation of the Hmip-ESI IEC energyCounterTwo sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the  device."""
        super().__init__(
            hap,
            device,
            key=ESI_TYPE_ENERGY_COUNTER_USAGE_LOW_TARIFF,
            value_fn=lambda channel: channel.energyCounterTwo,
            type_fn=lambda channel: channel.energyCounterTwoType,
        )


class HmipEsiIecEnergyCounterInputSingleTariff(HmipEsiSensorEntity):
    """Representation of the Hmip-ESI IEC energyCounterThree sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the device."""
        super().__init__(
            hap,
            device,
            key=ESI_TYPE_ENERGY_COUNTER_INPUT_SINGLE_TARIFF,
            value_fn=lambda channel: channel.energyCounterThree,
            type_fn=lambda channel: channel.energyCounterThreeType,
        )


class HmipEsiGasCurrentGasFlow(HmipEsiSensorEntity):
    """Representation of the Hmip-ESI Gas currentGasFlow sensor."""

    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the device."""
        super().__init__(
            hap,
            device,
            key="CurrentGasFlow",
            value_fn=lambda channel: channel.currentGasFlow,
            type_fn=lambda channel: "CurrentGasFlow",
        )


class HmipEsiGasGasVolume(HmipEsiSensorEntity):
    """Representation of the Hmip-ESI Gas gasVolume sensor."""

    _attr_device_class = SensorDeviceClass.GAS
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the device."""
        super().__init__(
            hap,
            device,
            key="GasVolume",
            value_fn=lambda channel: channel.gasVolume,
            type_fn=lambda channel: "GasVolume",
        )


class HmipEsiLedCurrentPowerConsumption(HmipEsiSensorEntity):
    """Representation of the Hmip-ESI LED currentPowerConsumption sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the device."""
        super().__init__(
            hap,
            device,
            key="CurrentPowerConsumption",
            value_fn=lambda channel: channel.currentPowerConsumption,
            type_fn=lambda channel: "CurrentPowerConsumption",
        )


class HmipEsiLedEnergyCounterHighTariff(HmipEsiSensorEntity):
    """Representation of the Hmip-ESI LED energyCounterOne sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the device."""
        super().__init__(
            hap,
            device,
            key=ESI_TYPE_ENERGY_COUNTER_USAGE_HIGH_TARIFF,
            value_fn=lambda channel: channel.energyCounterOne,
            type_fn=lambda channel: ESI_TYPE_ENERGY_COUNTER_USAGE_HIGH_TARIFF,
        )


class HomematicipPassageDetectorDeltaCounter(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP passage detector delta counter."""

    @property
    def native_value(self) -> int:
        """Return the passage detector delta counter value."""
        return self._device.leftRightCounterDelta

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the delta counter."""
        state_attr = super().extra_state_attributes

        state_attr[ATTR_LEFT_COUNTER] = self._device.leftCounter
        state_attr[ATTR_RIGHT_COUNTER] = self._device.rightCounter

        return state_attr


def _get_wind_direction(wind_direction_degree: float) -> str:
    """Convert wind direction degree to named direction."""
    if 11.25 <= wind_direction_degree < 33.75:
        return "NNE"
    if 33.75 <= wind_direction_degree < 56.25:
        return "NE"
    if 56.25 <= wind_direction_degree < 78.75:
        return "ENE"
    if 78.75 <= wind_direction_degree < 101.25:
        return "E"
    if 101.25 <= wind_direction_degree < 123.75:
        return "ESE"
    if 123.75 <= wind_direction_degree < 146.25:
        return "SE"
    if 146.25 <= wind_direction_degree < 168.75:
        return "SSE"
    if 168.75 <= wind_direction_degree < 191.25:
        return "S"
    if 191.25 <= wind_direction_degree < 213.75:
        return "SSW"
    if 213.75 <= wind_direction_degree < 236.25:
        return "SW"
    if 236.25 <= wind_direction_degree < 258.75:
        return "WSW"
    if 258.75 <= wind_direction_degree < 281.25:
        return "W"
    if 281.25 <= wind_direction_degree < 303.75:
        return "WNW"
    if 303.75 <= wind_direction_degree < 326.25:
        return "NW"
    if 326.25 <= wind_direction_degree < 348.75:
        return "NNW"
    return "N"
