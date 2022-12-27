"""Constants for the Trydan integration."""
from __future__ import annotations

DOMAIN = "v2c"
DATA_CONFIG_ENTRY = "config_entry"
CONF_COAP_PORT = 502  # ModbusTCP Port
ATTR_LAST_UPDATE = "last_update"
CHARGER_NAME_KEY = "name"

CHARGER_DATA_KEY = "config_data"
CHARGER_SERIAL_NUMBER_KEY = "serial_number"

# write
PAUSE_STATE_KEY = "pause_state"
LOCK_KEY = "lock"
PROMGRAM_KEY = "promgram"
INTENSITY_KEY = "intensity"
DYNAMIC_KEY = "dynamic"
PAYMENT_KEY = "payment"
OCPP_KEY = "ocpp"

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
