"""Constants for the Trydan integration."""
DOMAIN = "v2c"

CHARGE_STATES = [
    "A: Esperando Vehículo",
    "B: Conectando Vehículo",
    "C: Cargando Vehículo",
]
SLAVE_ERROR = ["No error", "Error message", "Communication error"]
PAUSE_DAYNAMIC = [
    "Dynamic Control Modulation Working",
    "Dynamic Control Modulation Pause",
]
DYNAMIC_POWER_MODE = [
    "Timed Power Enable",
    "Timed Power Disabled",
    "Timed Power Disable and Exclusive Mode Setted",
    "Timed Power Disable and Min Power Mode Setted",
    "Timed Power Disable and Grid+FV Mode Setted",
    "Timed Power Disable and Stop Mode Setted",
]

# read
CHARGE_STATE_KEY = "charge_state"
CHARGE_POWER_KEY = "charge_power"
CHARGE_ENERGY_KEY = "charge_energy"
SLAVE_ERROR_KEY = "slave_error"
CHARGE_TIME_KEY = "charge_time"
PWM_VALUE_KEY = "pwm_value"
HOUSE_POWER_KEY = "house_power"
FV_POWER_KEY = "fv_power"
PAUSE_STATE_READ_KEY = "pause_state_read"
LOCK_READ_KEY = "lock_read"
PROMGRAM_READ_KEY = "promgram_read"
INTENSITY_READ_KEY = "intensity_read"
DYNAMIC_READ_KEY = "dynamic_read"
PAYMENT_READ_KEY = "payment_read"
OCPP_READ_KEY = "ocpp_read"
MIN_INTENSITY_READ_KEY = "min_intensity_read"
MAX_INTENSITY_READ_KEY = "max_intensity_read"
PAUSE_DYNAMIC_READ_KEY = "pause_dynamic_read"
DYNAMIC_POWER_MODE_READ_KEY = "dynamic_power_mode_read"
CONTRACTED_POWER_READ_KEY = "contracted_power_read"
