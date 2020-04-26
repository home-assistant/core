"""Constants for the Tesla Powerwall integration."""

DOMAIN = "powerwall"

POWERWALL_OBJECT = "powerwall"
POWERWALL_COORDINATOR = "coordinator"
POWERWALL_API_CHANGED = "api_changed"

UPDATE_INTERVAL = 30

ATTR_REGION = "region"
ATTR_GRID_CODE = "grid_code"
ATTR_FREQUENCY = "frequency"
ATTR_ENERGY_EXPORTED = "energy_exported"
ATTR_ENERGY_IMPORTED = "energy_imported"
ATTR_INSTANT_AVERAGE_VOLTAGE = "instant_average_voltage"
ATTR_NOMINAL_SYSTEM_POWER = "nominal_system_power_kW"

STATUS_VERSION = "version"

POWERWALL_SITE_NAME = "site_name"

POWERWALL_API_METERS = "meters"
POWERWALL_API_CHARGE = "charge"
POWERWALL_API_GRID_STATUS = "grid_status"
POWERWALL_API_SITEMASTER = "sitemaster"
POWERWALL_API_STATUS = "status"
POWERWALL_API_DEVICE_TYPE = "device_type"
POWERWALL_API_SITE_INFO = "site_info"
POWERWALL_API_SERIAL_NUMBERS = "serial_numbers"

POWERWALL_HTTP_SESSION = "http_session"

POWERWALL_BATTERY_METER = "battery"

# We only declare charging if they are getting
# at least 40W incoming as measuring the fields
# is not an exact science because of interference
CHARGING_MARGIN_OF_ERROR = -40

MODEL = "PowerWall 2"
MANUFACTURER = "Tesla"

ENERGY_KILO_WATT = "kW"
