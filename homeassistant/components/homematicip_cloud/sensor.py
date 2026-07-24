"""Support for HomematicIP Cloud sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, override

from homematicip.base.enums import FunctionalChannelType, ValveState
from homematicip.base.functionalChannels import (
    FloorTerminalBlockMechanicChannel,
    FunctionalChannel,
)
from homematicip.device import (
    Device,
    EnergySensorsInterface,
    FloorTerminalBlock6,
    FloorTerminalBlock10,
    FloorTerminalBlock12,
    HeatingThermostat,
    HeatingThermostatCompact,
    HeatingThermostatEvo,
    HomeControlAccessPoint,
    LightSensor,
    MotionDetectorIndoor,
    MotionDetectorOutdoor,
    PassageDetector,
    PresenceDetectorIndoor,
    RoomControlDeviceAnalog,
    RotaryHandleSensor,
    SmokeDetector,
    SoilMoistureSensorInterface,
    SwitchMeasuring,
    TemperatureDifferenceSensor2,
    TemperatureHumiditySensorDisplay,
    TemperatureHumiditySensorOutdoor,
    TemperatureHumiditySensorWithoutDisplay,
    TiltVibrationSensor,
    WateringActuator,
    WeatherSensor,
    WeatherSensorPlus,
    WeatherSensorPro,
    WiredFloorTerminalBlock12,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    UnitOfDensity,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP
from .helpers import get_channels_from_device, smoke_detector_channel_data_exists


@dataclass(frozen=True, kw_only=True)
class HmipSmokeDetectorSensorDescription(SensorEntityDescription):
    """Describes HmIP smoke detector sensor entity."""

    value_fn: Callable[[SmokeDetector], StateType | datetime]
    channel_field: str  # Field name in the raw channel payload


SMOKE_DETECTOR_SENSORS: tuple[HmipSmokeDetectorSensorDescription, ...] = (
    HmipSmokeDetectorSensorDescription(
        key="dirt_level",
        translation_key="smoke_detector_dirt_level",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        channel_field="dirtLevel",
        value_fn=lambda d: (
            round(d.dirtLevel * 100, 1) if d.dirtLevel is not None else None
        ),
    ),
    HmipSmokeDetectorSensorDescription(
        key="smoke_alarm_counter",
        translation_key="smoke_detector_alarm_counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        channel_field="smokeAlarmCounter",
        value_fn=lambda d: d.smokeAlarmCounter,
    ),
    HmipSmokeDetectorSensorDescription(
        key="smoke_test_counter",
        translation_key="smoke_detector_test_counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        channel_field="smokeTestCounter",
        value_fn=lambda d: d.smokeTestCounter,
    ),
    HmipSmokeDetectorSensorDescription(
        key="last_smoke_alarm",
        translation_key="smoke_detector_last_alarm",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        channel_field="lastSmokeAlarmTimestamp",
        value_fn=lambda d: (
            datetime.fromtimestamp(d.lastSmokeAlarmTimestamp / 1000, tz=UTC)
            if d.lastSmokeAlarmTimestamp
            else None
        ),
    ),
    HmipSmokeDetectorSensorDescription(
        key="last_smoke_test",
        translation_key="smoke_detector_last_test",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        channel_field="lastSmokeTestTimestamp",
        value_fn=lambda d: (
            datetime.fromtimestamp(d.lastSmokeTestTimestamp / 1000, tz=UTC)
            if d.lastSmokeTestTimestamp
            else None
        ),
    ),
)


@dataclass(frozen=True, kw_only=True)
class HmipSensorDescription[_DeviceT: Device](SensorEntityDescription):
    """Describe a simple HomematicIP sensor."""

    value_fn: Callable[[_DeviceT], StateType]
    exists_fn: Callable[[_DeviceT], bool] = lambda _: True
    extra_attrs_fn: Callable[[_DeviceT], dict[str, Any]] | None = None
    icon_fn: Callable[[_DeviceT], str] | None = None
    channel: int


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
WINDOW_STATE_VALUES = ["open", "closed", "tilted"]


def _temperature_value(device: Device) -> float | None:
    if hasattr(device, "valveActualTemperature"):
        return device.valveActualTemperature
    return getattr(device, "actualTemperature", None)


def _temperature_extras(device: Device) -> dict[str, Any]:
    offset = getattr(device, "temperatureOffset", None)
    if offset is not None:
        return {ATTR_TEMPERATURE_OFFSET: offset}
    return {}


def _illuminance_value(device: Device) -> float | None:
    if hasattr(device, "averageIllumination"):
        return device.averageIllumination
    return getattr(device, "illumination", None)


def _illuminance_extras(device: Device) -> dict[str, Any]:
    return {
        attr_key: value
        for attr, attr_key in ILLUMINATION_DEVICE_ATTRIBUTES.items()
        if (value := getattr(device, attr, None)) is not None
    }


def _absolute_humidity_value(device: Device) -> float | None:
    value = getattr(device, "vaporAmount", None)
    if value is None or value == "":
        return None
    return value


def _windspeed_extras(device: Device) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    wind_direction = getattr(device, "windDirection", None)
    if wind_direction is not None:
        extras[ATTR_WIND_DIRECTION] = _get_wind_direction(wind_direction)
    wind_direction_variation = getattr(device, "windDirectionVariation", None)
    if wind_direction_variation is not None:
        extras[ATTR_WIND_DIRECTION_VARIATION] = wind_direction_variation
    return extras


def _heating_valve_value(device: Device) -> int | None:
    if device.valveState != ValveState.ADAPTION_DONE:
        return None
    return round(device.valvePosition * 100)


def _heating_valve_icon(device: Device) -> str:
    if device.valveState != ValveState.ADAPTION_DONE:
        return "mdi:alert"
    return "mdi:radiator"


def _passage_counter_extras(device: Device) -> dict[str, Any]:
    return {
        ATTR_LEFT_COUNTER: device.leftCounter,
        ATTR_RIGHT_COUNTER: device.rightCounter,
    }


def _tilt_angle_value(device: Device) -> int | None:
    channels = getattr(device, "functionalChannels", None)
    if not channels:
        return None
    ch = (
        channels.get(1)
        if isinstance(channels, dict)
        else (channels[1] if len(channels) > 1 else None)
    )
    return getattr(ch, "absoluteAngle", None) if ch else None


TEMPERATURE_DESC = HmipSensorDescription[Device](
    key="temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_temperature_value,
    extra_attrs_fn=_temperature_extras,
    channel=1,
)

HUMIDITY_DESC = HmipSensorDescription[Device](
    key="humidity",
    device_class=SensorDeviceClass.HUMIDITY,
    native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: d.humidity,
    channel=1,
)

ABSOLUTE_HUMIDITY_DESC = HmipSensorDescription[Device](
    key="absolute_humidity",
    device_class=SensorDeviceClass.ABSOLUTE_HUMIDITY,
    native_unit_of_measurement=UnitOfDensity.GRAMS_PER_CUBIC_METER,
    suggested_display_precision=1,
    suggested_unit_of_measurement=UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_absolute_humidity_value,
    channel=1,
)

ILLUMINANCE_DESC = HmipSensorDescription[Device](
    key="illuminance",
    device_class=SensorDeviceClass.ILLUMINANCE,
    native_unit_of_measurement=LIGHT_LUX,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_illuminance_value,
    extra_attrs_fn=_illuminance_extras,
    channel=1,
)

POWER_DESC = HmipSensorDescription[Device](
    key="power",
    device_class=SensorDeviceClass.POWER,
    native_unit_of_measurement=UnitOfPower.WATT,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: d.currentPowerConsumption,
    channel=1,
)

ENERGY_DESC = HmipSensorDescription[Device](
    key="energy",
    device_class=SensorDeviceClass.ENERGY,
    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    state_class=SensorStateClass.TOTAL_INCREASING,
    value_fn=lambda d: d.energyCounter,
    channel=1,
)

WIND_SPEED_DESC = HmipSensorDescription[Device](
    key="wind_speed",
    device_class=SensorDeviceClass.WIND_SPEED,
    native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: d.windSpeed,
    extra_attrs_fn=_windspeed_extras,
    channel=1,
)

TODAY_RAIN_DESC = HmipSensorDescription[Device](
    key="today_rain",
    translation_key="today_rain",
    device_class=SensorDeviceClass.PRECIPITATION,
    native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: round(d.todayRainCounter, 2),
    channel=1,
)

TEMPERATURE_EXTERNAL_CH1_DESC = HmipSensorDescription[Device](
    key="temperature_external_ch1",
    translation_key="channel_1_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: d.temperatureExternalOne,
    channel=1,
)

TEMPERATURE_EXTERNAL_CH2_DESC = HmipSensorDescription[Device](
    key="temperature_external_ch2",
    translation_key="channel_2_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: d.temperatureExternalTwo,
    channel=1,
)

TEMPERATURE_EXTERNAL_DELTA_DESC = HmipSensorDescription[Device](
    key="temperature_external_delta",
    translation_key="delta_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda d: d.temperatureExternalDelta,
    channel=1,
)

DUTY_CYCLE_DESC = HmipSensorDescription[Device](
    key="duty_cycle",
    translation_key="duty_cycle",
    native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    icon="mdi:access-point-network",
    value_fn=lambda d: d.dutyCycleLevel,
    channel=0,
)

VALVE_POSITION_DESC = HmipSensorDescription[Device](
    key="valve_position",
    translation_key="heating",
    native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
    value_fn=_heating_valve_value,
    icon_fn=_heating_valve_icon,
    channel=1,
)

PASSAGE_COUNTER_DESC = HmipSensorDescription[Device](
    key="passage_counter",
    value_fn=lambda d: d.leftRightCounterDelta,
    extra_attrs_fn=_passage_counter_extras,
    channel=1,
)

TILT_ANGLE_DESC = HmipSensorDescription[Device](
    key="tilt_angle",
    translation_key="tilt_angle",
    native_unit_of_measurement=DEGREE,
    state_class=SensorStateClass.MEASUREMENT_ANGLE,
    value_fn=_tilt_angle_value,
    channel=1,
)


# Keys must not subclass each other so each device matches one key; the setup
# loop breaks after the first match (enforced by
# test_simple_sensor_descriptions_no_overlap).
SENSOR_DESCRIPTIONS_BY_DEVICE: dict[
    type[Device], tuple[HmipSensorDescription[Device], ...]
] = {
    HomeControlAccessPoint: (DUTY_CYCLE_DESC,),
    HeatingThermostat: (VALVE_POSITION_DESC, TEMPERATURE_DESC),
    HeatingThermostatCompact: (VALVE_POSITION_DESC, TEMPERATURE_DESC),
    HeatingThermostatEvo: (VALVE_POSITION_DESC, TEMPERATURE_DESC),
    TemperatureHumiditySensorDisplay: (
        TEMPERATURE_DESC,
        HUMIDITY_DESC,
        ABSOLUTE_HUMIDITY_DESC,
    ),
    TemperatureHumiditySensorWithoutDisplay: (
        TEMPERATURE_DESC,
        HUMIDITY_DESC,
        ABSOLUTE_HUMIDITY_DESC,
    ),
    TemperatureHumiditySensorOutdoor: (
        TEMPERATURE_DESC,
        HUMIDITY_DESC,
        ABSOLUTE_HUMIDITY_DESC,
    ),
    RoomControlDeviceAnalog: (TEMPERATURE_DESC,),
    LightSensor: (ILLUMINANCE_DESC,),
    MotionDetectorIndoor: (ILLUMINANCE_DESC,),
    MotionDetectorOutdoor: (ILLUMINANCE_DESC,),
    PresenceDetectorIndoor: (ILLUMINANCE_DESC,),
    SwitchMeasuring: (POWER_DESC, ENERGY_DESC),
    PassageDetector: (PASSAGE_COUNTER_DESC,),
    TemperatureDifferenceSensor2: (
        TEMPERATURE_EXTERNAL_CH1_DESC,
        TEMPERATURE_EXTERNAL_CH2_DESC,
        TEMPERATURE_EXTERNAL_DELTA_DESC,
    ),
    TiltVibrationSensor: (TILT_ANGLE_DESC,),
    WeatherSensor: (
        TEMPERATURE_DESC,
        HUMIDITY_DESC,
        ILLUMINANCE_DESC,
        WIND_SPEED_DESC,
        ABSOLUTE_HUMIDITY_DESC,
    ),
    WeatherSensorPlus: (
        TEMPERATURE_DESC,
        HUMIDITY_DESC,
        ILLUMINANCE_DESC,
        WIND_SPEED_DESC,
        TODAY_RAIN_DESC,
        ABSOLUTE_HUMIDITY_DESC,
    ),
    WeatherSensorPro: (
        TEMPERATURE_DESC,
        HUMIDITY_DESC,
        ILLUMINANCE_DESC,
        WIND_SPEED_DESC,
        TODAY_RAIN_DESC,
        ABSOLUTE_HUMIDITY_DESC,
    ),
}


def get_device_handlers(hap: HomematicipHAP) -> dict[type, Callable]:
    """Return a mapping of device types to handler functions.

    Covers multi-channel and special-setup sensor entities only;
    ``SENSOR_DESCRIPTIONS_BY_DEVICE`` handles all simple non-multi-channel sensors.
    """
    return {
        RotaryHandleSensor: lambda device: [
            HomematicipWindowStateSensor(hap, device),
        ],
        TiltVibrationSensor: lambda device: [
            HomematicipTiltStateSensor(hap, device),
        ],
        WateringActuator: lambda device: [
            entity
            for ch in device.functionalChannels
            if ch.functionalChannelType
            == FunctionalChannelType.WATERING_ACTUATOR_CHANNEL
            for entity in (
                HomematicipWaterFlowSensor(
                    hap, device, channel=ch.index, post="currentWaterFlow"
                ),
                HomematicipWaterVolumeSensor(
                    hap,
                    device,
                    channel=ch.index,
                    post="waterVolume",
                    attribute="waterVolume",
                ),
                HomematicipWaterVolumeSinceOpenSensor(
                    hap,
                    device,
                    channel=ch.index,
                ),
            )
        ],
        EnergySensorsInterface: lambda device: _handle_energy_sensor_interface(
            hap, device
        ),
        SoilMoistureSensorInterface: lambda device: [
            HomematicipSoilMoistureSensor(hap, device),
            HomematicipSoilTemperatureSensor(hap, device),
        ],
    }


def _handle_energy_sensor_interface(
    hap: HomematicipHAP, device: Device
) -> list[HomematicipGenericEntity]:
    """Handle energy sensor interface devices."""
    result: list[HomematicipGenericEntity] = []
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
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP Cloud sensors from a config entry."""
    hap = config_entry.runtime_data
    entities: list[HomematicipGenericEntity] = []

    for device in hap.home.devices:
        for device_class, descriptions in SENSOR_DESCRIPTIONS_BY_DEVICE.items():
            if not isinstance(device, device_class):
                continue
            entities.extend(
                HomematicipSensor(hap, device, description)
                for description in descriptions
                if description.exists_fn(device)
            )
            # Each device matches at most one map key (enforced by
            # test_simple_sensor_descriptions_no_overlap), so further
            # iteration cannot add entities.
            break

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

    # Handle smoke detector extended sensors (e.g., HmIP-SWSD-2)
    entities.extend(
        HmipSmokeDetectorSensor(hap, device, description)
        for device in hap.home.devices
        if isinstance(device, SmokeDetector)
        for description in SMOKE_DETECTOR_SENSORS
        if smoke_detector_channel_data_exists(device, description.channel_field)
    )

    async_add_entities(entities)


class HomematicipWaterFlowSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP watering flow sensor."""

    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_MINUTE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, hap: HomematicipHAP, device: Device, channel: int, post: str
    ) -> None:
        """Initialize the watering flow sensor device."""
        super().__init__(
            hap,
            device,
            post=post,
            channel=channel,
            is_multi_channel=True,
            feature_id="water_flow",
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state."""
        channel = self.get_channel_or_raise()
        return channel.waterFlow


class HomematicipWaterVolumeSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP watering volume sensor."""

    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        hap: HomematicipHAP,
        device: Device,
        channel: int,
        post: str,
        attribute: str,
        feature_id: str = "water_volume",
    ) -> None:
        """Initialize the watering volume sensor device."""
        super().__init__(
            hap,
            device,
            post=post,
            channel=channel,
            is_multi_channel=True,
            feature_id=feature_id,
        )
        self._attribute_name = attribute

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state."""
        return getattr(self.functional_channel, self._attribute_name, None)


class HomematicipWaterVolumeSinceOpenSensor(HomematicipWaterVolumeSensor):
    """Representation of the HomematicIP watering volume since open sensor."""

    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hap: HomematicipHAP, device: Device, channel: int) -> None:
        """Initialize the watering flow volume since open device."""
        super().__init__(
            hap,
            device,
            channel=channel,
            post="waterVolumeSinceOpen",
            attribute="waterVolumeSinceOpen",
            feature_id="water_volume_since_open",
        )


class HomematicipTiltStateSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP tilt sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = TILT_STATE_VALUES
    _attr_translation_key = "tilt_state"

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the tilt sensor device."""
        super().__init__(hap, device, post="Tilt State", feature_id="tilt_state")

    @property
    @override
    def native_value(self) -> str | None:
        """Return the state."""
        tilt_state = getattr(self.functional_channel, "tiltState", None)
        return tilt_state.lower() if tilt_state is not None else None

    @property
    @override
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


class HomematicipWindowStateSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP rotary handle window state sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = WINDOW_STATE_VALUES
    _attr_translation_key = "window_state"

    def __init__(self, hap: HomematicipHAP, device: RotaryHandleSensor) -> None:
        """Initialize the window state sensor."""
        super().__init__(
            hap, device, feature_id="window_state", use_description_name=True
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Return the state."""
        window_state = getattr(self._device, "windowState", None)
        return window_state.lower() if window_state is not None else None


class HomematicipFloorTerminalBlockMechanicChannelValve(
    HomematicipGenericEntity, SensorEntity
):
    """Representation of the HomematicIP floor terminal block."""

    _attr_native_unit_of_measurement = UnitOfRatio.PERCENTAGE
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
            feature_id="ftb_valve_position",
        )

    @property
    @override
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
    @override
    def native_value(self) -> int | None:
        """Return the floor terminal block valve position."""
        channel = next(
            channel
            for channel in self._device.functionalChannels
            if channel.index == self._channel
        )
        if channel.valveState != ValveState.ADAPTION_DONE:
            return None
        return round(channel.valvePosition * 100)


class HmipEsiSensorEntity(HomematicipGenericEntity, SensorEntity):
    """EntityDescription for HmIP-ESI Sensors."""

    def __init__(
        self,
        hap: HomematicipHAP,
        device: HomematicipGenericEntity,
        key: str,
        value_fn: Callable[[FunctionalChannel], StateType],
        type_fn: Callable[[FunctionalChannel], str],
        feature_id: str,
    ) -> None:
        """Initialize Sensor Entity."""
        super().__init__(
            hap=hap,
            device=device,
            channel=1,
            post=key,
            is_multi_channel=False,
            feature_id=feature_id,
        )

        self._value_fn = value_fn
        self._type_fn = type_fn

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the esi sensor."""
        state_attr = super().extra_state_attributes
        state_attr[ATTR_ESI_TYPE] = self._type_fn(self.functional_channel)

        return state_attr

    @property
    @override
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
            feature_id="esi_iec_power",
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
            feature_id="esi_iec_energy_high",
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
            feature_id="esi_iec_energy_low",
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
            feature_id="esi_iec_energy_input",
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
            feature_id="esi_gas_flow",
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
            feature_id="esi_gas_volume",
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
            feature_id="esi_led_power",
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
            feature_id="esi_led_energy_high",
        )


class HmipSmokeDetectorSensor(HomematicipGenericEntity, SensorEntity):
    """Sensor for HomematicIP smoke detector extended properties."""

    entity_description: HmipSmokeDetectorSensorDescription

    def __init__(
        self,
        hap: HomematicipHAP,
        device: SmokeDetector,
        description: HmipSmokeDetectorSensorDescription,
    ) -> None:
        """Initialize the smoke detector sensor."""
        super().__init__(hap, device, feature_id="smoke_detector_sensor")
        self.entity_description = description
        self._sensor_unique_id = f"{device.id}_{description.key}"

    @property
    @override
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._sensor_unique_id

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._device)


class HomematicipSensor[_DeviceT: Device](HomematicipGenericEntity, SensorEntity):
    """A description-driven HomematicIP sensor."""

    entity_description: HmipSensorDescription[_DeviceT]

    def __init__(
        self,
        hap: HomematicipHAP,
        device: _DeviceT,
        description: HmipSensorDescription[_DeviceT],
    ) -> None:
        """Initialize the described sensor."""
        super().__init__(
            hap,
            device,
            feature_id=description.key,
            channel=description.channel,
            use_description_name=True,
        )
        self.entity_description = description

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._device)

    @property
    @override
    def icon(self) -> str | None:
        """Return the icon."""
        if (parent_icon := super().icon) is not None:
            return parent_icon
        if self.entity_description.icon_fn is not None:
            return self.entity_description.icon_fn(self._device)
        return self.entity_description.icon

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        state_attr = super().extra_state_attributes
        if self.entity_description.extra_attrs_fn is not None:
            state_attr.update(self.entity_description.extra_attrs_fn(self._device))
        return state_attr


class HomematicipSoilMoistureSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP soil moisture sensor."""

    _attr_device_class = SensorDeviceClass.MOISTURE
    _attr_native_unit_of_measurement = UnitOfRatio.PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the soil moisture sensor device."""
        super().__init__(
            hap,
            device,
            post="Soil Moisture",
            channel=1,
            is_multi_channel=True,
            feature_id="soil_moisture",
        )

    @property
    @override
    def native_value(self) -> int | None:
        """Return the state."""
        if self.functional_channel is None:
            return None
        return self.functional_channel.soilMoisture


class HomematicipSoilTemperatureSensor(HomematicipGenericEntity, SensorEntity):
    """Representation of the HomematicIP soil temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the soil temperature sensor device."""
        super().__init__(
            hap,
            device,
            post="Soil Temperature",
            channel=1,
            is_multi_channel=True,
            feature_id="soil_temperature",
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state."""
        if self.functional_channel is None:
            return None
        return self.functional_channel.soilTemperature


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
