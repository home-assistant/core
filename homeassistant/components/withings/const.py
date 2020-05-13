"""Constants used by the Withings component."""
import homeassistant.const as const

DATA_MANAGER = "data_manager"

BASE_URL = "base_url"
CLIENT_ID = "client_id"
CLIENT_SECRET = "client_secret"
CODE = "code"
CONFIG = "config"
CREDENTIALS = "credentials"
DOMAIN = "withings"
LOG_NAMESPACE = "homeassistant.components.withings"
MEASURES = "measures"
PROFILE = "profile"
PROFILES = "profiles"

AUTH_CALLBACK_PATH = "/api/withings/authorize"
AUTH_CALLBACK_NAME = "withings:authorize"

THROTTLE_INTERVAL = 60
SCAN_INTERVAL = 60

STATE_UNKNOWN = const.STATE_UNKNOWN
STATE_AWAKE = "awake"
STATE_DEEP = "deep"
STATE_LIGHT = "light"
STATE_REM = "rem"

MEAS_BODY_TEMP_C = "body_temperature_c"
MEAS_BONE_MASS_KG = "bone_mass_kg"
MEAS_DIASTOLIC_MMHG = "diastolic_blood_pressure_mmhg"
MEAS_FAT_FREE_MASS_KG = "fat_free_mass_kg"
MEAS_FAT_MASS_KG = "fat_mass_kg"
MEAS_FAT_RATIO_PCT = "fat_ratio_pct"
MEAS_HEART_PULSE_BPM = "heart_pulse_bpm"
MEAS_HEIGHT_M = "height_m"
MEAS_HYDRATION = "hydration"
MEAS_MUSCLE_MASS_KG = "muscle_mass_kg"
MEAS_PWV = "pulse_wave_velocity"
MEAS_SKIN_TEMP_C = "skin_temperature_c"
MEAS_SLEEP_DEEP_DURATION_SECONDS = "sleep_deep_duration_seconds"
MEAS_SLEEP_HEART_RATE_AVERAGE = "sleep_heart_rate_average_bpm"
MEAS_SLEEP_HEART_RATE_MAX = "sleep_heart_rate_max_bpm"
MEAS_SLEEP_HEART_RATE_MIN = "sleep_heart_rate_min_bpm"
MEAS_SLEEP_LIGHT_DURATION_SECONDS = "sleep_light_duration_seconds"
MEAS_SLEEP_REM_DURATION_SECONDS = "sleep_rem_duration_seconds"
MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE = "sleep_respiratory_average_bpm"
MEAS_SLEEP_RESPIRATORY_RATE_MAX = "sleep_respiratory_max_bpm"
MEAS_SLEEP_RESPIRATORY_RATE_MIN = "sleep_respiratory_min_bpm"
MEAS_SLEEP_TOSLEEP_DURATION_SECONDS = "sleep_tosleep_duration_seconds"
MEAS_SLEEP_TOWAKEUP_DURATION_SECONDS = "sleep_towakeup_duration_seconds"
MEAS_SLEEP_WAKEUP_COUNT = "sleep_wakeup_count"
MEAS_SLEEP_WAKEUP_DURATION_SECONDS = "sleep_wakeup_duration_seconds"
MEAS_SPO2_PCT = "spo2_pct"
MEAS_SYSTOLIC_MMGH = "systolic_blood_pressure_mmhg"
MEAS_TEMP_C = "temperature_c"
MEAS_WEIGHT_KG = "weight_kg"

UOM_BEATS_PER_MINUTE = "bpm"
UOM_BREATHS_PER_MINUTE = f"br/{const.TIME_MINUTES}"
UOM_FREQUENCY = "times"
UOM_MMHG = "mmhg"
UOM_LENGTH_M = const.LENGTH_METERS
UOM_TEMP_C = const.TEMP_CELSIUS
