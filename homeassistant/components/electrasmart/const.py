"""Constants for the Electra Air Conditioner integration."""

DOMAIN = "electrasmart"

CONF_PHONE_NUMBER = "phone_number"
CONF_OTP = "one_time_password"
CONF_IMEI = "imei"
SCAN_INTERVAL_SEC = 30
API_DELAY = 5
CONSECUTIVE_FAILURE_THRESHOLD = 4
UNAVAILABLE_THRESH_SEC = 120
PRESET_NONE = "None"
PRESET_SHABAT = "Shabat"

# The Electra API returns I_RAT/I_CALC_AT telemetry values left-shifted by 8 bits
# (×256). Raw values above this threshold are treated as unscaled and right-shifted.
SENSOR_TEMP_SCALE_THRESHOLD = 100
SENSOR_TEMP_SHIFT_BITS = 8
