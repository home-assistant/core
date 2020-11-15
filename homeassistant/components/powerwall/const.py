"""Constants for the Tesla Powerwall integration."""

DOMAIN = "powerwall"

POWERWALL_OBJECT = "powerwall"
POWERWALL_COORDINATOR = "coordinator"
POWERWALL_API_CHANGED = "api_changed"

UPDATE_INTERVAL = 30

ATTR_FREQUENCY = "frequency"
ATTR_ENERGY_EXPORTED = "energy_exported_(in_kW)"
ATTR_ENERGY_IMPORTED = "energy_imported_(in_kW)"
ATTR_INSTANT_AVERAGE_VOLTAGE = "instant_average_voltage"
ATTR_IS_ACTIVE = "is_active"

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

MODEL = "PowerWall 2"
MANUFACTURER = "Tesla"

ENERGY_KILO_WATT = "kW"
