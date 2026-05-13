"""Tests for the Place device shadow data models."""

from homeassistant.components.gentex_place.const import AlarmStatus
from homeassistant.components.gentex_place.models import PlaceDeviceShadow

FULL_SHADOW = {
    "state": {
        "reported": {
            "deviceId": "device-001",
            "model": "MODEL-X",
            "fwPackageId": "fw-1.0",
            "autoUpdate": True,
            "secureBuild": True,
            "lastUpdated": "2024-01-01T00:00:00Z",
            "inChattyMode": False,
            "traceLoggingDiagnosticMode": False,
            "temperatureC": 22.5,
            "humidity": 45,
            "boardTempC": 30.0,
            "airQualityIndex": 50,
            "airQualityPm25": 10,
            "airQualityPm100": 20,
            "irFrontScatter": 1,
            "irBackScatter": 2,
            "blueFrontScatter": 3,
            "blueBackScatter": 4,
            "coAccumulation": 5,
            "coPpm": 6,
            "methanePpm": 7,
            "vocIndex": 8,
            "coAlarmStatus": 0,
            "heatAlarmStatus": 3,
            "smokeAlarmStatus": 5,
            "explosiveGasAlarmStatus": 1,
            "aqiAlarmStatus": 2,
            "vocAlarmStatus": 4,
            "coAlarmLastUpdated": "2024-01-01T00:00:00Z",
            "heatAlarmLastUpdated": "2024-01-02T00:00:00Z",
            "smokeAlarmLastUpdated": "2024-01-03T00:00:00Z",
            "explosiveGasAlarmLastUpdated": "2024-01-04T00:00:00Z",
            "aqiAlarmLastUpdated": "2024-01-05T00:00:00Z",
            "vocAlarmLastUpdated": "2024-01-06T00:00:00Z",
            "coAlarmStartTime": "2024-01-01T00:00:00Z",
            "heatAlarmStartTime": "2024-01-02T00:00:00Z",
            "smokeAlarmStartTime": "2024-01-03T00:00:00Z",
            "explosiveGasAlarmStartTime": "2024-01-04T00:00:00Z",
            "aqiAlarmStartTime": "2024-01-05T00:00:00Z",
            "vocAlarmStartTime": "2024-01-06T00:00:00Z",
            "motionSensitivity": 3,
            "desiredShadowError": 0,
            "batteryStatus": 1,
            "removeDevice": False,
            "flappingFaultsBitMap": 0,
            "wifiSignalStrength": -50,
            "wifiSsid": "MyNetwork",
            "manufactureDate": "2024-01-01T00:00:00Z",
            "otaInProgress": False,
            "deviceOrientation": 1,
            "aqiHmiEnabled": True,
            "vocHmiEnabled": True,
            "batteryLowPreWarning": False,
            "faults": {
                "manufacturingTest": 0,
                "methaneSensor": 1,
                "stuckButton": 0,
                "corruptNvm": 0,
                "heatSensor": 0,
                "coSensor": 0,
                "smokeSensor": 0,
                "battery": 0,
                "voc": 0,
                "tempHumiditySensor": 0,
                "airQuality": 0,
                "motionSensor": 0,
                "als": 0,  # codespell:ignore als
            },
            "endOfLife": {"system": 0, "methane": 0},
            "nightLightSettings": {
                "ambientLight": True,
                "motionDetection": False,
                "on": True,
                "rgbaLed": {"red": 255, "green": 128, "blue": 0, "alpha": 255},
            },
            "audioSettings": {
                "liveStreamVolume": 70,
                "whiteNoiseVolume": 30,
                "whiteNoise": True,
                "songIndex": 2,
            },
            "cameraSettings": {
                "enabled": True,
                "events": [1, 2, 3],
                "liveViewSignalingStatus": 1,
                "liveViewStreamingStatus": 0,
                "liveViewStreamingSessionsCount": 0,
            },
            "surveillanceSettings": {
                "enabled": False,
                "timer": {"enabled": False, "seconds": 0},
            },
            "testingSettings": {
                "alarmState": 0,
                "smokeHeatResult": True,
                "methaneResult": False,
                "coResult": True,
                "lastTested": "2024-06-15T12:00:00Z",
            },
            "timezone": {
                "name": "America/New_York",
                "posix": "EST5EDT,M3.2.0,M11.1.0",
            },
            "temperatureAlertThresholds": {
                "enabled": True,
                "highEnabled": True,
                "highValue": 35.0,
                "lowEnabled": True,
                "lowValue": 10.0,
            },
            "humidityAlertThresholds": {
                "enabled": True,
                "highEnabled": True,
                "highValue": 70.0,
                "lowEnabled": False,
                "lowValue": 20.0,
            },
        }
    }
}


def test_from_shadow_full() -> None:
    """Test parsing a complete shadow payload."""
    shadow = PlaceDeviceShadow.from_shadow(FULL_SHADOW)

    # Identity
    assert shadow.device_id == "device-001"
    assert shadow.model == "MODEL-X"
    assert shadow.fw_package_id == "fw-1.0"
    assert shadow.auto_update is True
    assert shadow.secure_build is True

    # Environmental
    assert shadow.temperature_c == 22.5
    assert shadow.humidity == 45
    assert shadow.board_temp_c == 30.0
    assert shadow.air_quality_index == 50

    # Optical / gas
    assert shadow.ir_front_scatter == 1
    assert shadow.co_ppm == 6
    assert shadow.methane_ppm == 7
    assert shadow.voc_index == 8

    # Alarm statuses
    assert shadow.co_alarm_status is AlarmStatus.IDLE
    assert shadow.heat_alarm_status is AlarmStatus.ALARM
    assert shadow.smoke_alarm_status is AlarmStatus.HUSHED
    assert shadow.explosive_gas_alarm_status is AlarmStatus.TEST
    assert shadow.aqi_alarm_status is AlarmStatus.PRE_ALARM
    assert shadow.voc_alarm_status is AlarmStatus.CRITICAL_ALARM

    # Alarm timestamps
    assert shadow.co_alarm_last_updated == "2024-01-01T00:00:00Z"
    assert shadow.heat_alarm_start_time == "2024-01-02T00:00:00Z"

    # Device state
    assert shadow.wifi_ssid == "MyNetwork"
    assert shadow.wifi_signal_strength == -50
    assert shadow.battery_status == 1
    assert shadow.motion_sensitivity == 3
    assert shadow.device_orientation == 1

    # Faults
    assert shadow.faults.methane_sensor == 1
    assert shadow.faults.manufacturing_test == 0

    # Night light
    assert shadow.night_light_settings.on is True
    assert shadow.night_light_settings.ambient_light is True
    assert shadow.night_light_settings.rgba_led.red == 255
    assert shadow.night_light_settings.rgba_led.alpha == 255

    # Audio
    assert shadow.audio_settings.live_stream_volume == 70
    assert shadow.audio_settings.white_noise is True
    assert shadow.audio_settings.song_index == 2

    # Camera
    assert shadow.camera_settings.enabled is True
    assert shadow.camera_settings.events == [1, 2, 3]

    # Testing
    assert shadow.testing_settings.smoke_heat_result is True
    assert shadow.testing_settings.co_result is True
    assert shadow.testing_settings.last_tested == "2024-06-15T12:00:00Z"

    # Timezone
    assert shadow.timezone.name == "America/New_York"

    # Alert thresholds
    assert shadow.temperature_alert_thresholds.enabled is True
    assert shadow.temperature_alert_thresholds.high_value == 35.0
    assert shadow.humidity_alert_thresholds.low_enabled is False


def test_from_shadow_without_state_wrapper() -> None:
    """Test parsing a flat reported dict (no state.reported wrapper)."""
    reported = {
        "coAlarmStatus": 3,
        "heatAlarmStatus": 0,
        "smokeAlarmStatus": 5,
        "temperatureC": 25.0,
    }
    shadow = PlaceDeviceShadow.from_shadow(reported)

    assert shadow.co_alarm_status is AlarmStatus.ALARM
    assert shadow.heat_alarm_status is AlarmStatus.IDLE
    assert shadow.smoke_alarm_status is AlarmStatus.HUSHED
    assert shadow.temperature_c == 25.0


def test_from_shadow_empty() -> None:
    """Test parsing an empty shadow returns defaults."""
    shadow = PlaceDeviceShadow.from_shadow({})

    assert shadow.co_alarm_status is AlarmStatus.NOT_PRESENT
    assert shadow.heat_alarm_status is AlarmStatus.NOT_PRESENT
    assert shadow.smoke_alarm_status is AlarmStatus.NOT_PRESENT
    assert shadow.temperature_c is None
    assert shadow.device_id is None


def test_from_shadow_invalid_alarm_value() -> None:
    """Test that out-of-range alarm values default to NOT_PRESENT."""
    shadow = PlaceDeviceShadow.from_shadow({"coAlarmStatus": 99})

    assert shadow.co_alarm_status is AlarmStatus.NOT_PRESENT


def test_from_shadow_null_alarm_value() -> None:
    """Test that null alarm values default to NOT_PRESENT."""
    shadow = PlaceDeviceShadow.from_shadow({"coAlarmStatus": None})

    assert shadow.co_alarm_status is AlarmStatus.NOT_PRESENT


def test_merge_sparse_update() -> None:
    """Test that a sparse update only changes provided fields."""
    shadow = PlaceDeviceShadow.from_shadow(FULL_SHADOW)

    assert shadow.co_alarm_status is AlarmStatus.IDLE
    assert shadow.temperature_c == 22.5
    assert shadow.wifi_ssid == "MyNetwork"

    shadow.merge(
        {
            "state": {
                "reported": {
                    "coAlarmStatus": 3,
                    "temperatureC": 30.0,
                }
            }
        }
    )

    # Updated fields
    assert shadow.co_alarm_status is AlarmStatus.ALARM
    assert shadow.temperature_c == 30.0

    # Unchanged fields
    assert shadow.heat_alarm_status is AlarmStatus.ALARM
    assert shadow.smoke_alarm_status is AlarmStatus.HUSHED
    assert shadow.wifi_ssid == "MyNetwork"
    assert shadow.humidity == 45


def test_merge_nested_object() -> None:
    """Test that merging a nested object replaces it entirely."""
    shadow = PlaceDeviceShadow.from_shadow(FULL_SHADOW)

    assert shadow.night_light_settings.on is True
    assert shadow.night_light_settings.rgba_led.red == 255

    shadow.merge(
        {
            "state": {
                "reported": {
                    "nightLightSettings": {
                        "ambientLight": False,
                        "motionDetection": True,
                        "on": False,
                        "rgbaLed": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0,
                        },
                    }
                }
            }
        }
    )

    assert shadow.night_light_settings.on is False
    assert shadow.night_light_settings.motion_detection is True
    assert shadow.night_light_settings.rgba_led.red == 0


def test_merge_alarm_timestamps() -> None:
    """Test that alarm timestamps can be updated via merge."""
    shadow = PlaceDeviceShadow()

    shadow.merge(
        {
            "state": {
                "reported": {
                    "smokeAlarmStatus": 3,
                    "smokeAlarmLastUpdated": "2024-06-15T12:00:00Z",
                    "smokeAlarmStartTime": "2024-06-15T11:59:00Z",
                }
            }
        }
    )

    assert shadow.smoke_alarm_status is AlarmStatus.ALARM
    assert shadow.smoke_alarm_last_updated == "2024-06-15T12:00:00Z"
    assert shadow.smoke_alarm_start_time == "2024-06-15T11:59:00Z"


def test_alarm_status_enum_values() -> None:
    """Test AlarmStatus enum has correct integer mappings."""
    assert AlarmStatus.IDLE == 0
    assert AlarmStatus.TEST == 1
    assert AlarmStatus.PRE_ALARM == 2
    assert AlarmStatus.ALARM == 3
    assert AlarmStatus.CRITICAL_ALARM == 4
    assert AlarmStatus.HUSHED == 5
    assert AlarmStatus.NOT_PRESENT == 6
