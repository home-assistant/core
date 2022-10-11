"""Constants for Key Atome."""
from datetime import timedelta

# Tools
DEBUG_FLAG = False

# Domain name
DOMAIN = "atome"

# Config flow
DATA_COORDINATOR = "coordinator"

# Conf atome_linky_number
CONF_ATOME_LINKY_NUMBER = "atome_linky_number"
DEFAULT_ATOME_LINKY_NUMBER = 1

# Sensor default name
DEFAULT_NAME = "Atome"

# sensor name
LOGIN_STAT_NAME_SUFFIX = "_Login_Stat"
LIVE_NAME_SUFFIX = " Live Power"
DAILY_NAME_SUFFIX = " Daily"
WEEKLY_NAME_SUFFIX = " Weekly"
MONTHLY_NAME_SUFFIX = " Monthly"
DIAGNOSTIC_NAME_SUFFIX = "_Diagnostic"
# period name
PERIOD_NAME_SUFFIX = "_Period"

# device name
DEVICE_NAME_SUFFIX = " Device"
DEVICE_CONF_URL = "https://www.totalenergies.fr/clients"

# Attribution
ATTRIBUTION = "Data provided by TotalEnergies"

# Attribute sensor name
ATTR_PREVIOUS_PERIOD_USAGE = "previous_consumption"
ATTR_PREVIOUS_PERIOD_PRICE = "previous_price"
ATTR_PERIOD_PRICE = "price"
ATTR_PREVIOUS_PERIOD_REF_DAY = "previous_ref_day"
ATTR_PERIOD_REF_DAY = "ref_day"

# Scan interval (avoid synchronisation to lower request per seconds on server)
LOGIN_STAT_SCAN_INTERVAL = timedelta(hours=1, minutes=30, seconds=13)
LIVE_SCAN_INTERVAL = timedelta(seconds=30)
PERIOD_SCAN_INTERVAL = timedelta(minutes=5, seconds=3)

# Type to call py key atome
LIVE_TYPE = "live"
LOGIN_STAT_TYPE = "login_stat"
PERIOD_CONSUMPTION_TYPE = "period_consumption"

# Round price
ROUND_PRICE = 2

# max error theshold
MAX_SERVER_ERROR_THRESHOLD = 5

# export const
DAILY_PERIOD_TYPE = "day"
WEEKLY_PERIOD_TYPE = "week"
MONTHLY_PERIOD_TYPE = "month"
