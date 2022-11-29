"""Constants for the Landis+Gyr Heat Meter integration."""

from datetime import timedelta

DOMAIN = "landisgyr_heat_meter"

ULTRAHEAT_TIMEOUT = 30  # reading the IR port can take some time
POLLING_INTERVAL = timedelta(days=1)  # Polling is only daily to prevent battery drain.

# Keys used to check for GJ or MWH
MWH_IDENTITY_KEY = "heat_usage_mwh"
GJ_IDENTITY_KEY = "heat_usage_gj"

# Keys that are energy unit specific
MWH_ONLY_KEYS = ["heat_usage", "heat_previous_year"]
GJ_ONLY_KEYS = ["heat_usage_gj", "heat_previous_year_gj"]
