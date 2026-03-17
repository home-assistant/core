"""Constants for the Photoptimizer integration."""

DOMAIN = "photoptimizer"

# Configuration keys for optimizer inputs
CONF_HORIZON_HOURS = "horizon_hours"  # optional, default 24
CONF_RESOLUTION = "resolution"  # "hourly"
CONF_TIMEZONE = "timezone"  # optional, defaults to Home Assistant timezone

# Energy price
CONF_ELECTRICITY_PRICE_ENTITY = "electricity_price_entity"  # required
CONF_PRICE_INCLUDE_VAT = "price_include_vat"  # optional, default False

# Forecasts
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_AZIMUTH = "azimuth"
CONF_KWP = "kwp"
CONF_DECLINATION = "declination"
CONF_API_KEY = "api_key"

CONF_LOAD_FORECAST_ENTITY = "load_forecast_entity"  # optional
CONF_PV_FORECAST_ENTITY = "pv_forecast_entity"  # optional
CONF_EMHASS_URL = "emhass_url"
CONF_EMHASS_TOKEN = "emhass_token"  # optional

# Battery and inverter configuration
CONF_BATTERY_CAPACITY_KWH = "battery_capacity_kwh"  # required
CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"  # required
CONF_BATTERY_SOC_RESERVE_PERCENT = (
    "battery_soc_reserve_percent"  # optional, default 20%
)
CONF_BATTERY_EFFICIENCY_ROUND_TRIP = (
    "battery_efficiency_round_trip"  # optional, default 100%
)

CONF_MAX_INVERTER_CURRENT_AMP = (
    "max_inverter_current_amp"  # optional, inverter amperage limit
)
CONF_CURRENT_SOLAR_PRODUCTION_ENTITY = "current_solar_production_entity"  # required
CONF_CURRENT_CONSUMPTION_ENTITY = "current_consumption_entity"  # required
CONF_GRID_POWER_ENTITY = "grid_power_entity"  # required


CONF_WEAR_COST_PER_KWH = "wear_cost_per_kwh"  # optional, default 0.0


# Default values
DEFAULT_HORIZON_HOURS = 24
DEFAULT_RESOLUTION = "hourly"
DEFAULT_PRICE_INCLUDE_VAT = False
DEFAULT_BATTERY_SOC_RESERVE_PERCENT = 20.0
DEFAULT_WEAR_COST_PER_KWH = 0.0
DEFAULT_BATTERY_EFFICIENCY_ROUND_TRIP = 100.0
DEFAULT_EMHASS_URL = "http://localhost:5000"
