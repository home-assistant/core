"""Data models for the Place device shadow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import AlarmStatus


@dataclass
class PlaceFaults:
    """Device fault flags."""

    manufacturing_test: int = 0
    methane_sensor: int = 0
    stuck_button: int = 0
    corrupt_nvm: int = 0
    heat_sensor: int = 0
    co_sensor: int = 0
    smoke_sensor: int = 0
    battery: int = 0
    voc: int = 0
    temp_humidity_sensor: int = 0
    air_quality: int = 0
    motion_sensor: int = 0
    als: int = 0  # codespell:ignore als


@dataclass
class PlaceEndOfLife:
    """End-of-life counters."""

    system: int = 0
    methane: int = 0


@dataclass
class PlaceRgbaLed:
    """RGBA LED color."""

    red: int = 0
    green: int = 0
    blue: int = 0
    alpha: int = 0


@dataclass
class PlaceNightLightSettings:
    """Night light configuration."""

    ambient_light: bool = False
    motion_detection: bool = False
    on: bool = False
    rgba_led: PlaceRgbaLed = field(default_factory=PlaceRgbaLed)


@dataclass
class PlaceAudioSettings:
    """Audio configuration."""

    live_stream_volume: int = 50
    white_noise_volume: int = 50
    white_noise: bool = False
    song_index: int = 0


@dataclass
class PlaceCameraSettings:
    """Camera configuration."""

    enabled: bool = False
    events: list[int] = field(default_factory=list)
    live_view_signaling_status: int = 0
    live_view_streaming_status: int = 0
    live_view_streaming_sessions_count: int = 0


@dataclass
class PlaceSurveillanceTimer:
    """Surveillance timer."""

    enabled: bool = False
    seconds: int = 0


@dataclass
class PlaceSurveillanceSettings:
    """Surveillance configuration."""

    enabled: bool = False
    timer: PlaceSurveillanceTimer = field(default_factory=PlaceSurveillanceTimer)


@dataclass
class PlaceTestingSettings:
    """Testing configuration."""

    alarm_state: int = 0
    smoke_heat_result: bool = False
    methane_result: bool = False
    co_result: bool = False
    last_tested: str | None = None


@dataclass
class PlaceTimezone:
    """Timezone info."""

    name: str = ""
    posix: str = ""


@dataclass
class PlaceAlertThresholds:
    """Temperature or humidity alert thresholds."""

    enabled: bool = False
    high_enabled: bool = False
    high_value: float = 0.0
    low_enabled: bool = False
    low_value: float = 0.0


@dataclass
class PlaceDeviceShadow:
    """Full device shadow state."""

    # Identity / firmware
    device_id: str | None = None
    model: str | None = None
    fw_package_id: str | None = None
    auto_update: bool = False
    secure_build: bool = False
    last_updated: str | None = None

    # Diagnostics
    in_chatty_mode: bool = False
    trace_logging_diagnostic_mode: bool = False

    # Environmental sensors
    temperature_c: float | None = None
    humidity: int | None = None
    board_temp_c: float | None = None
    air_quality_index: int | None = None
    air_quality_pm25: int | None = None
    air_quality_pm100: int | None = None

    # Optical / gas sensors
    ir_front_scatter: int = 0
    ir_back_scatter: int = 0
    blue_front_scatter: int = 0
    blue_back_scatter: int = 0
    co_accumulation: int = 0
    co_ppm: int = 0
    methane_ppm: int = 0
    voc_index: int = 0

    # Alarm statuses
    co_alarm_status: AlarmStatus = AlarmStatus.NOT_PRESENT
    heat_alarm_status: AlarmStatus = AlarmStatus.NOT_PRESENT
    smoke_alarm_status: AlarmStatus = AlarmStatus.NOT_PRESENT
    explosive_gas_alarm_status: AlarmStatus = AlarmStatus.NOT_PRESENT
    aqi_alarm_status: AlarmStatus = AlarmStatus.NOT_PRESENT
    voc_alarm_status: AlarmStatus = AlarmStatus.NOT_PRESENT

    # Alarm timestamps
    co_alarm_last_updated: str | None = None
    heat_alarm_last_updated: str | None = None
    smoke_alarm_last_updated: str | None = None
    explosive_gas_alarm_last_updated: str | None = None
    aqi_alarm_last_updated: str | None = None
    voc_alarm_last_updated: str | None = None

    co_alarm_start_time: str | None = None
    heat_alarm_start_time: str | None = None
    smoke_alarm_start_time: str | None = None
    explosive_gas_alarm_start_time: str | None = None
    aqi_alarm_start_time: str | None = None
    voc_alarm_start_time: str | None = None

    # Device state
    motion_sensitivity: int = 0
    desired_shadow_error: int = 0
    battery_status: int = 0
    remove_device: bool = False
    flapping_faults_bit_map: int = 0
    wifi_signal_strength: int = 0
    wifi_ssid: str | None = None
    manufacture_date: str | None = None
    ota_in_progress: bool = False
    device_orientation: int = 0
    aqi_hmi_enabled: bool = True
    voc_hmi_enabled: bool = True
    battery_low_pre_warning: bool = False

    # Nested objects
    faults: PlaceFaults = field(default_factory=PlaceFaults)
    end_of_life: PlaceEndOfLife = field(default_factory=PlaceEndOfLife)
    night_light_settings: PlaceNightLightSettings = field(
        default_factory=PlaceNightLightSettings
    )
    audio_settings: PlaceAudioSettings = field(default_factory=PlaceAudioSettings)
    camera_settings: PlaceCameraSettings = field(default_factory=PlaceCameraSettings)
    surveillance_settings: PlaceSurveillanceSettings = field(
        default_factory=PlaceSurveillanceSettings
    )
    testing_settings: PlaceTestingSettings = field(default_factory=PlaceTestingSettings)
    timezone: PlaceTimezone = field(default_factory=PlaceTimezone)
    temperature_alert_thresholds: PlaceAlertThresholds = field(
        default_factory=PlaceAlertThresholds
    )
    humidity_alert_thresholds: PlaceAlertThresholds = field(
        default_factory=PlaceAlertThresholds
    )

    @staticmethod
    def from_shadow(shadow: dict[str, Any]) -> PlaceDeviceShadow:
        """Parse a full shadow from a raw dict."""
        reported = shadow.get("state", shadow).get("reported", shadow)
        return _parse_reported(reported)

    def merge(self, partial: dict[str, Any]) -> None:
        """Merge a sparse shadow update into the current state."""
        reported = partial.get("state", partial).get("reported", partial)
        _merge_reported(self, reported)


def _parse_alarm(value: Any) -> AlarmStatus:
    """Convert a raw shadow value to an AlarmStatus."""
    if value is None:
        return AlarmStatus.NOT_PRESENT
    try:
        return AlarmStatus(int(value))
    except ValueError, KeyError:
        return AlarmStatus.NOT_PRESENT


def _parse_faults(data: dict[str, Any]) -> PlaceFaults:
    return PlaceFaults(
        manufacturing_test=data.get("manufacturingTest", 0),
        methane_sensor=data.get("methaneSensor", 0),
        stuck_button=data.get("stuckButton", 0),
        corrupt_nvm=data.get("corruptNvm", 0),
        heat_sensor=data.get("heatSensor", 0),
        co_sensor=data.get("coSensor", 0),
        smoke_sensor=data.get("smokeSensor", 0),
        battery=data.get("battery", 0),
        voc=data.get("voc", 0),
        temp_humidity_sensor=data.get("tempHumiditySensor", 0),
        air_quality=data.get("airQuality", 0),
        motion_sensor=data.get("motionSensor", 0),
        als=data.get("als", 0),  # codespell:ignore als
    )


def _parse_end_of_life(data: dict[str, Any]) -> PlaceEndOfLife:
    return PlaceEndOfLife(
        system=data.get("system", 0),
        methane=data.get("methane", 0),
    )


def _parse_rgba_led(data: dict[str, Any]) -> PlaceRgbaLed:
    return PlaceRgbaLed(
        red=data.get("red", 0),
        green=data.get("green", 0),
        blue=data.get("blue", 0),
        alpha=data.get("alpha", 0),
    )


def _parse_night_light(data: dict[str, Any]) -> PlaceNightLightSettings:
    return PlaceNightLightSettings(
        ambient_light=data.get("ambientLight", False),
        motion_detection=data.get("motionDetection", False),
        on=data.get("on", False),
        rgba_led=_parse_rgba_led(data.get("rgbaLed", {})),
    )


def _parse_audio(data: dict[str, Any]) -> PlaceAudioSettings:
    return PlaceAudioSettings(
        live_stream_volume=data.get("liveStreamVolume", 50),
        white_noise_volume=data.get("whiteNoiseVolume", 50),
        white_noise=data.get("whiteNoise", False),
        song_index=data.get("songIndex", 0),
    )


def _parse_camera(data: dict[str, Any]) -> PlaceCameraSettings:
    return PlaceCameraSettings(
        enabled=data.get("enabled", False),
        events=list(data.get("events") or []),
        live_view_signaling_status=data.get("liveViewSignalingStatus", 0),
        live_view_streaming_status=data.get("liveViewStreamingStatus", 0),
        live_view_streaming_sessions_count=data.get(
            "liveViewStreamingSessionsCount", 0
        ),
    )


def _parse_surveillance(data: dict[str, Any]) -> PlaceSurveillanceSettings:
    timer_data = data.get("timer", {})
    return PlaceSurveillanceSettings(
        enabled=data.get("enabled", False),
        timer=PlaceSurveillanceTimer(
            enabled=timer_data.get("enabled", False),
            seconds=timer_data.get("seconds", 0),
        ),
    )


def _parse_testing(data: dict[str, Any]) -> PlaceTestingSettings:
    return PlaceTestingSettings(
        alarm_state=data.get("alarmState", 0),
        smoke_heat_result=data.get("smokeHeatResult", False),
        methane_result=data.get("methaneResult", False),
        co_result=data.get("coResult", False),
        last_tested=data.get("lastTested"),
    )


def _parse_timezone(data: dict[str, Any]) -> PlaceTimezone:
    return PlaceTimezone(
        name=data.get("name", ""),
        posix=data.get("posix", ""),
    )


def _parse_alert_thresholds(data: dict[str, Any]) -> PlaceAlertThresholds:
    return PlaceAlertThresholds(
        enabled=data.get("enabled", False),
        high_enabled=data.get("highEnabled", False),
        high_value=data.get("highValue", 0.0),
        low_enabled=data.get("lowEnabled", False),
        low_value=data.get("lowValue", 0.0),
    )


def _parse_reported(reported: dict[str, Any]) -> PlaceDeviceShadow:
    """Build a full PlaceDeviceShadow from a reported dict."""
    return PlaceDeviceShadow(
        # Identity / firmware
        device_id=reported.get("deviceId"),
        model=reported.get("model"),
        fw_package_id=reported.get("fwPackageId"),
        auto_update=reported.get("autoUpdate", False),
        secure_build=reported.get("secureBuild", False),
        last_updated=reported.get("lastUpdated"),
        # Diagnostics
        in_chatty_mode=reported.get("inChattyMode", False),
        trace_logging_diagnostic_mode=reported.get("traceLoggingDiagnosticMode", False),
        # Environmental sensors
        temperature_c=reported.get("temperatureC"),
        humidity=reported.get("humidity"),
        board_temp_c=reported.get("boardTempC"),
        air_quality_index=reported.get("airQualityIndex"),
        air_quality_pm25=reported.get("airQualityPm25"),
        air_quality_pm100=reported.get("airQualityPm100"),
        # Optical / gas sensors
        ir_front_scatter=reported.get("irFrontScatter", 0),
        ir_back_scatter=reported.get("irBackScatter", 0),
        blue_front_scatter=reported.get("blueFrontScatter", 0),
        blue_back_scatter=reported.get("blueBackScatter", 0),
        co_accumulation=reported.get("coAccumulation", 0),
        co_ppm=reported.get("coPpm", 0),
        methane_ppm=reported.get("methanePpm", 0),
        voc_index=reported.get("vocIndex", 0),
        # Alarm statuses
        co_alarm_status=_parse_alarm(reported.get("coAlarmStatus")),
        heat_alarm_status=_parse_alarm(reported.get("heatAlarmStatus")),
        smoke_alarm_status=_parse_alarm(reported.get("smokeAlarmStatus")),
        explosive_gas_alarm_status=_parse_alarm(
            reported.get("explosiveGasAlarmStatus")
        ),
        aqi_alarm_status=_parse_alarm(reported.get("aqiAlarmStatus")),
        voc_alarm_status=_parse_alarm(reported.get("vocAlarmStatus")),
        # Alarm timestamps
        co_alarm_last_updated=reported.get("coAlarmLastUpdated"),
        heat_alarm_last_updated=reported.get("heatAlarmLastUpdated"),
        smoke_alarm_last_updated=reported.get("smokeAlarmLastUpdated"),
        explosive_gas_alarm_last_updated=reported.get("explosiveGasAlarmLastUpdated"),
        aqi_alarm_last_updated=reported.get("aqiAlarmLastUpdated"),
        voc_alarm_last_updated=reported.get("vocAlarmLastUpdated"),
        co_alarm_start_time=reported.get("coAlarmStartTime"),
        heat_alarm_start_time=reported.get("heatAlarmStartTime"),
        smoke_alarm_start_time=reported.get("smokeAlarmStartTime"),
        explosive_gas_alarm_start_time=reported.get("explosiveGasAlarmStartTime"),
        aqi_alarm_start_time=reported.get("aqiAlarmStartTime"),
        voc_alarm_start_time=reported.get("vocAlarmStartTime"),
        # Device state
        motion_sensitivity=reported.get("motionSensitivity", 0),
        desired_shadow_error=reported.get("desiredShadowError", 0),
        battery_status=reported.get("batteryStatus", 0),
        remove_device=reported.get("removeDevice", False),
        flapping_faults_bit_map=reported.get("flappingFaultsBitMap", 0),
        wifi_signal_strength=reported.get("wifiSignalStrength", 0),
        wifi_ssid=reported.get("wifiSsid"),
        manufacture_date=reported.get("manufactureDate"),
        ota_in_progress=reported.get("otaInProgress", False),
        device_orientation=reported.get("deviceOrientation", 0),
        aqi_hmi_enabled=reported.get("aqiHmiEnabled", True),
        voc_hmi_enabled=reported.get("vocHmiEnabled", True),
        battery_low_pre_warning=reported.get("batteryLowPreWarning", False),
        # Nested objects
        faults=_parse_faults(reported.get("faults", {})),
        end_of_life=_parse_end_of_life(reported.get("endOfLife", {})),
        night_light_settings=_parse_night_light(reported.get("nightLightSettings", {})),
        audio_settings=_parse_audio(reported.get("audioSettings", {})),
        camera_settings=_parse_camera(reported.get("cameraSettings", {})),
        surveillance_settings=_parse_surveillance(
            reported.get("surveillanceSettings", {})
        ),
        testing_settings=_parse_testing(reported.get("testingSettings", {})),
        timezone=_parse_timezone(reported.get("timezone", {})),
        temperature_alert_thresholds=_parse_alert_thresholds(
            reported.get("temperatureAlertThresholds", {})
        ),
        humidity_alert_thresholds=_parse_alert_thresholds(
            reported.get("humidityAlertThresholds", {})
        ),
    )


# Mapping from camelCase JSON keys to dataclass field names for flat scalars.
_FIELD_MAP: dict[str, str] = {
    "deviceId": "device_id",
    "model": "model",
    "fwPackageId": "fw_package_id",
    "autoUpdate": "auto_update",
    "secureBuild": "secure_build",
    "lastUpdated": "last_updated",
    "inChattyMode": "in_chatty_mode",
    "traceLoggingDiagnosticMode": "trace_logging_diagnostic_mode",
    "temperatureC": "temperature_c",
    "humidity": "humidity",
    "boardTempC": "board_temp_c",
    "airQualityIndex": "air_quality_index",
    "airQualityPm25": "air_quality_pm25",
    "airQualityPm100": "air_quality_pm100",
    "irFrontScatter": "ir_front_scatter",
    "irBackScatter": "ir_back_scatter",
    "blueFrontScatter": "blue_front_scatter",
    "blueBackScatter": "blue_back_scatter",
    "coAccumulation": "co_accumulation",
    "coPpm": "co_ppm",
    "methanePpm": "methane_ppm",
    "vocIndex": "voc_index",
    "coAlarmLastUpdated": "co_alarm_last_updated",
    "heatAlarmLastUpdated": "heat_alarm_last_updated",
    "smokeAlarmLastUpdated": "smoke_alarm_last_updated",
    "explosiveGasAlarmLastUpdated": "explosive_gas_alarm_last_updated",
    "aqiAlarmLastUpdated": "aqi_alarm_last_updated",
    "vocAlarmLastUpdated": "voc_alarm_last_updated",
    "coAlarmStartTime": "co_alarm_start_time",
    "heatAlarmStartTime": "heat_alarm_start_time",
    "smokeAlarmStartTime": "smoke_alarm_start_time",
    "explosiveGasAlarmStartTime": "explosive_gas_alarm_start_time",
    "aqiAlarmStartTime": "aqi_alarm_start_time",
    "vocAlarmStartTime": "voc_alarm_start_time",
    "motionSensitivity": "motion_sensitivity",
    "desiredShadowError": "desired_shadow_error",
    "batteryStatus": "battery_status",
    "removeDevice": "remove_device",
    "flappingFaultsBitMap": "flapping_faults_bit_map",
    "wifiSignalStrength": "wifi_signal_strength",
    "wifiSsid": "wifi_ssid",
    "manufactureDate": "manufacture_date",
    "otaInProgress": "ota_in_progress",
    "deviceOrientation": "device_orientation",
    "aqiHmiEnabled": "aqi_hmi_enabled",
    "vocHmiEnabled": "voc_hmi_enabled",
    "batteryLowPreWarning": "battery_low_pre_warning",
}

_ALARM_FIELD_MAP: dict[str, str] = {
    "coAlarmStatus": "co_alarm_status",
    "heatAlarmStatus": "heat_alarm_status",
    "smokeAlarmStatus": "smoke_alarm_status",
    "explosiveGasAlarmStatus": "explosive_gas_alarm_status",
    "aqiAlarmStatus": "aqi_alarm_status",
    "vocAlarmStatus": "voc_alarm_status",
}

_NESTED_PARSERS: dict[str, tuple[str, Any]] = {
    "faults": ("faults", _parse_faults),
    "endOfLife": ("end_of_life", _parse_end_of_life),
    "nightLightSettings": ("night_light_settings", _parse_night_light),
    "audioSettings": ("audio_settings", _parse_audio),
    "cameraSettings": ("camera_settings", _parse_camera),
    "surveillanceSettings": ("surveillance_settings", _parse_surveillance),
    "testingSettings": ("testing_settings", _parse_testing),
    "timezone": ("timezone", _parse_timezone),
    "temperatureAlertThresholds": (
        "temperature_alert_thresholds",
        _parse_alert_thresholds,
    ),
    "humidityAlertThresholds": (
        "humidity_alert_thresholds",
        _parse_alert_thresholds,
    ),
}


def _merge_reported(shadow: PlaceDeviceShadow, reported: dict[str, Any]) -> None:
    """Merge a sparse reported dict into an existing shadow (mutates in place)."""
    for json_key, field_name in _FIELD_MAP.items():
        if json_key in reported:
            setattr(shadow, field_name, reported[json_key])

    for json_key, field_name in _ALARM_FIELD_MAP.items():
        if json_key in reported:
            setattr(shadow, field_name, _parse_alarm(reported[json_key]))

    for json_key, (field_name, parser) in _NESTED_PARSERS.items():
        if json_key in reported:
            setattr(shadow, field_name, parser(reported[json_key]))
