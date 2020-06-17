"""Constants used by the Withings component."""
from enum import Enum

import homeassistant.const as const

CONF_PROFILES = "profiles"
CONF_USE_WEBHOOK = "use_webhook"

DATA_MANAGER = "data_manager"

CONFIG = "config"
DOMAIN = "withings"
LOG_NAMESPACE = "homeassistant.components.withings"
PROFILE = "profile"
PUSH_HANDLER = "push_handler"
CONF_WEBHOOK_URL = "webhook_url"


class Measurement(Enum):
    """Measurement supported by the withings integration."""

    BODY_TEMP_C = "body_temperature_c"
    BONE_MASS_KG = "bone_mass_kg"
    DIASTOLIC_MMHG = "diastolic_blood_pressure_mmhg"
    FAT_FREE_MASS_KG = "fat_free_mass_kg"
    FAT_MASS_KG = "fat_mass_kg"
    FAT_RATIO_PCT = "fat_ratio_pct"
    HEART_PULSE_BPM = "heart_pulse_bpm"
    HEIGHT_M = "height_m"
    HYDRATION = "hydration"
    IN_BED = "in_bed"
    MUSCLE_MASS_KG = "muscle_mass_kg"
    PWV = "pulse_wave_velocity"
    SKIN_TEMP_C = "skin_temperature_c"
    SLEEP_BREATHING_DISTURBANCES_INTENSITY = "sleep_breathing_disturbances_intensity"
    SLEEP_DEEP_DURATION_SECONDS = "sleep_deep_duration_seconds"
    SLEEP_HEART_RATE_AVERAGE = "sleep_heart_rate_average_bpm"
    SLEEP_HEART_RATE_MAX = "sleep_heart_rate_max_bpm"
    SLEEP_HEART_RATE_MIN = "sleep_heart_rate_min_bpm"
    SLEEP_LIGHT_DURATION_SECONDS = "sleep_light_duration_seconds"
    SLEEP_REM_DURATION_SECONDS = "sleep_rem_duration_seconds"
    SLEEP_RESPIRATORY_RATE_AVERAGE = "sleep_respiratory_average_bpm"
    SLEEP_RESPIRATORY_RATE_MAX = "sleep_respiratory_max_bpm"
    SLEEP_RESPIRATORY_RATE_MIN = "sleep_respiratory_min_bpm"
    SLEEP_SCORE = "sleep_score"
    SLEEP_SNORING = "sleep_snoring"
    SLEEP_SNORING_EPISODE_COUNT = "sleep_snoring_eposode_count"
    SLEEP_TOSLEEP_DURATION_SECONDS = "sleep_tosleep_duration_seconds"
    SLEEP_TOWAKEUP_DURATION_SECONDS = "sleep_towakeup_duration_seconds"
    SLEEP_WAKEUP_COUNT = "sleep_wakeup_count"
    SLEEP_WAKEUP_DURATION_SECONDS = "sleep_wakeup_duration_seconds"
    SPO2_PCT = "spo2_pct"
    SYSTOLIC_MMGH = "systolic_blood_pressure_mmhg"
    TEMP_C = "temperature_c"
    WEIGHT_KG = "weight_kg"


UOM_BEATS_PER_MINUTE = "bpm"
UOM_BREATHS_PER_MINUTE = f"br/{const.TIME_MINUTES}"
UOM_FREQUENCY = "times"
UOM_MMHG = "mmhg"
UOM_LENGTH_M = const.LENGTH_METERS
UOM_TEMP_C = const.TEMP_CELSIUS
