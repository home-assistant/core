"""Constants for the Toon integration."""
from homeassistant.const import ENERGY_KILO_WATT_HOUR

DOMAIN = 'toon'

DATA_TOON = 'toon'
DATA_TOON_CONFIG = 'toon_config'
DATA_TOON_CLIENT = 'toon_client'

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_DISPLAY = 'display'
CONF_TENANT = 'tenant'

DEFAULT_MAX_TEMP = 30.0
DEFAULT_MIN_TEMP = 6.0

CURRENCY_EUR = 'EUR'
POWER_WATT = 'W'
POWER_KWH = ENERGY_KILO_WATT_HOUR
RATIO_PERCENT = '%'
VOLUME_CM3 = 'CM3'
VOLUME_M3 = 'M3'
