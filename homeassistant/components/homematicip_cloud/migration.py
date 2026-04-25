"""Unique ID migration for HomematicIP Cloud entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _MigrationConfig:
    """Configuration for migrating a single entity class to the new unique_id format."""

    feature_id: str
    channel: int | None = None
    is_group: bool = False


UNIQUE_ID_MIGRATION_MAP: dict[str, _MigrationConfig] = {
    # binary_sensor
    "HomematicipCloudConnectionSensor": _MigrationConfig(
        "cloud_connection", is_group=True
    ),
    "HomematicipAccelerationSensor": _MigrationConfig("acceleration", channel=1),
    "HomematicipTiltVibrationSensor": _MigrationConfig("tilt_vibration", channel=1),
    "HomematicipMultiContactInterface": _MigrationConfig("contact"),
    "HomematicipContactInterface": _MigrationConfig("contact", channel=1),
    "HomematicipShutterContact": _MigrationConfig("shutter_contact", channel=1),
    "HomematicipMotionDetector": _MigrationConfig("motion", channel=1),
    "HomematicipPresenceDetector": _MigrationConfig("presence", channel=1),
    "HomematicipSmokeDetector": _MigrationConfig("smoke", channel=1),
    "HomematicipWaterDetector": _MigrationConfig("water", channel=1),
    "HomematicipStormSensor": _MigrationConfig("storm", channel=1),
    "HomematicipRainSensor": _MigrationConfig("rain", channel=1),
    "HomematicipSunshineSensor": _MigrationConfig("sunshine", channel=1),
    "HomematicipBatterySensor": _MigrationConfig("battery", channel=0),
    "HomematicipPluggableMainsFailureSurveillanceSensor": _MigrationConfig(
        "mains_failure", channel=1
    ),
    "HomematicipSecurityZoneSensorGroup": _MigrationConfig(
        "security_zone", is_group=True
    ),
    "HomematicipSecuritySensorGroup": _MigrationConfig("security", is_group=True),
    "HomematicipFullFlushLockControllerLocked": _MigrationConfig(
        "lock_locked", channel=1
    ),
    "HomematicipFullFlushLockControllerGlassBreak": _MigrationConfig(
        "glass_break", channel=1
    ),
    "HomematicipSmokeDetectorChamberDegraded": _MigrationConfig(
        "chamber_degraded", channel=1
    ),
    # sensor
    "HomematicipAccesspointDutyCycle": _MigrationConfig("duty_cycle", channel=0),
    "HomematicipHeatingThermostat": _MigrationConfig("valve_position", channel=1),
    "HomematicipHumiditySensor": _MigrationConfig("humidity", channel=1),
    "HomematicipTemperatureSensor": _MigrationConfig("temperature", channel=1),
    "HomematicipAbsoluteHumiditySensor": _MigrationConfig(
        "absolute_humidity", channel=1
    ),
    "HomematicipIlluminanceSensor": _MigrationConfig("illuminance", channel=1),
    "HomematicipPowerSensor": _MigrationConfig("power", channel=1),
    "HomematicipEnergySensor": _MigrationConfig("energy", channel=1),
    "HomematicipWindspeedSensor": _MigrationConfig("wind_speed", channel=1),
    "HomematicipTodayRainSensor": _MigrationConfig("today_rain", channel=1),
    "HomematicipPassageDetectorDeltaCounter": _MigrationConfig(
        "passage_counter", channel=1
    ),
    "HomematicipWaterFlowSensor": _MigrationConfig("water_flow"),
    "HomematicipWaterVolumeSensor": _MigrationConfig("water_volume"),
    "HomematicipWaterVolumeSinceOpenSensor": _MigrationConfig(
        "water_volume_since_open"
    ),
    "HomematicipTiltAngleSensor": _MigrationConfig("tilt_angle", channel=1),
    "HomematicipTiltStateSensor": _MigrationConfig("tilt_state", channel=1),
    "HomematicipFloorTerminalBlockMechanicChannelValve": _MigrationConfig(
        "ftb_valve_position"
    ),
    "HomematicpTemperatureExternalSensorCh1": _MigrationConfig(
        "temperature_external_ch1", channel=1
    ),
    "HomematicpTemperatureExternalSensorCh2": _MigrationConfig(
        "temperature_external_ch2", channel=1
    ),
    "HomematicpTemperatureExternalSensorDelta": _MigrationConfig(
        "temperature_external_delta", channel=1
    ),
    "HmipEsiIecPowerConsumption": _MigrationConfig("esi_iec_power", channel=1),
    "HmipEsiIecEnergyCounterHighTariff": _MigrationConfig(
        "esi_iec_energy_high", channel=1
    ),
    "HmipEsiIecEnergyCounterLowTariff": _MigrationConfig(
        "esi_iec_energy_low", channel=1
    ),
    "HmipEsiIecEnergyCounterInputSingleTariff": _MigrationConfig(
        "esi_iec_energy_input", channel=1
    ),
    "HmipEsiGasCurrentGasFlow": _MigrationConfig("esi_gas_flow", channel=1),
    "HmipEsiGasGasVolume": _MigrationConfig("esi_gas_volume", channel=1),
    "HmipEsiLedCurrentPowerConsumption": _MigrationConfig("esi_led_power", channel=1),
    "HmipEsiLedEnergyCounterHighTariff": _MigrationConfig(
        "esi_led_energy_high", channel=1
    ),
    "HomematicipSoilMoistureSensor": _MigrationConfig("soil_moisture", channel=1),
    "HomematicipSoilTemperatureSensor": _MigrationConfig("soil_temperature", channel=1),
    # light
    "HomematicipLight": _MigrationConfig("light", channel=1),
    "HomematicipLightHS": _MigrationConfig("light"),
    "HomematicipLightMeasuring": _MigrationConfig("light", channel=1),
    "HomematicipMultiDimmer": _MigrationConfig("dimmer"),
    "HomematicipDimmer": _MigrationConfig("dimmer", channel=1),
    "HomematicipNotificationLight": _MigrationConfig("notification_light"),
    "HomematicipNotificationLightV2": _MigrationConfig("notification_light"),
    "HomematicipColorLight": _MigrationConfig("color_light", channel=1),
    "HomematicipOpticalSignalLight": _MigrationConfig(
        "optical_signal_light", channel=1
    ),
    "HomematicipCombinationSignallingLight": _MigrationConfig(
        "combination_signalling_light", channel=1
    ),
    # switch
    "HomematicipMultiSwitch": _MigrationConfig("switch"),
    "HomematicipSwitch": _MigrationConfig("switch", channel=1),
    "HomematicipGroupSwitch": _MigrationConfig("switch", is_group=True),
    "HomematicipSwitchMeasuring": _MigrationConfig("switch", channel=1),
    # cover
    "HomematicipBlindModule": _MigrationConfig("blind", channel=1),
    "HomematicipMultiCoverShutter": _MigrationConfig("shutter"),
    "HomematicipCoverShutter": _MigrationConfig("shutter", channel=1),
    "HomematicipMultiCoverSlats": _MigrationConfig("slats"),
    "HomematicipCoverSlats": _MigrationConfig("slats", channel=1),
    "HomematicipGarageDoorModule": _MigrationConfig("garage_door", channel=1),
    "HomematicipCoverShutterGroup": _MigrationConfig("shutter", is_group=True),
    # climate
    "HomematicipHeatingGroup": _MigrationConfig("climate", is_group=True),
    # weather
    "HomematicipWeatherSensor": _MigrationConfig("weather", channel=1),
    "HomematicipWeatherSensorPro": _MigrationConfig("weather", channel=1),
    "HomematicipHomeWeather": _MigrationConfig("home_weather", is_group=True),
    # valve
    "HomematicipWateringValve": _MigrationConfig("watering"),
    # lock
    "HomematicipDoorLockDrive": _MigrationConfig("lock", channel=1),
    # button
    "HomematicipGarageDoorControllerButton": _MigrationConfig(
        "garage_button", channel=1
    ),
    "HomematicipFullFlushLockControllerButton": _MigrationConfig(
        "lock_opener_button", channel=1
    ),
    # event
    "HomematicipDoorBellEvent": _MigrationConfig("doorbell", channel=1),
    # alarm_control_panel
    "HomematicipAlarmControlPanelEntity": _MigrationConfig("alarm", is_group=True),
    # siren
    "HomematicipMP3Siren": _MigrationConfig("siren", channel=1),
}

# Sorted by length descending so longer class names match before shorter ones
# (e.g., "HomematicipSwitchMeasuring" before "HomematicipSwitch")
_SORTED_CLASS_NAMES = sorted(UNIQUE_ID_MIGRATION_MAP, key=len, reverse=True)

_CHANNEL_RE = re.compile(r"^Channel(\d+)_(.+)$")
_NOTIFICATION_LIGHT_RE = re.compile(r"^(Top|Bottom)_(.+)$")

_NOTIFICATION_LIGHT_CHANNEL_MAP = {"Top": 2, "Bottom": 3}


def _migrate_unique_id(old_unique_id: str) -> str | None:
    """Convert an old-format unique_id to the new format.

    Old formats:
      {ClassName}_{device_id}
      {ClassName}_Channel{N}_{device_id}
      {ClassName}_{Top|Bottom}_{device_id}  (NotificationLight only)

    New format:
      {device_id}_{channel}_{feature_id}    (device entities)
      {device_id}_{feature_id}              (group/home entities)
    """
    # Find the matching class name (longest first)
    matched_class: str | None = None
    for class_name in _SORTED_CLASS_NAMES:
        prefix = class_name + "_"
        if old_unique_id.startswith(prefix):
            matched_class = class_name
            break

    if matched_class is None:
        return None

    config = UNIQUE_ID_MIGRATION_MAP[matched_class]
    remainder = old_unique_id[len(matched_class) + 1 :]

    # Parse remainder to extract channel and device_id
    channel: int | None = None
    device_id: str

    # Check for Channel{N}_{rest} pattern
    channel_match = _CHANNEL_RE.match(remainder)
    if channel_match:
        channel = int(channel_match.group(1))
        device_id = channel_match.group(2)
    elif matched_class in (
        "HomematicipNotificationLight",
        "HomematicipNotificationLightV2",
    ):
        # Check for Top/Bottom pattern
        notif_match = _NOTIFICATION_LIGHT_RE.match(remainder)
        if notif_match:
            channel = _NOTIFICATION_LIGHT_CHANNEL_MAP[notif_match.group(1)]
            device_id = notif_match.group(2)
        else:
            device_id = remainder
            channel = config.channel
    else:
        device_id = remainder
        channel = config.channel

    # Build new unique_id
    if config.is_group:
        return f"{device_id}_{config.feature_id}"

    if channel is not None:
        return f"{device_id}_{channel}_{config.feature_id}"

    _LOGGER.warning(
        "Cannot determine channel for unique_id: %s",
        old_unique_id,
    )
    return None
