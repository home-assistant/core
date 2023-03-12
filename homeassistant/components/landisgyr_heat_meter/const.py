"""Constants for the Landis+Gyr Heat Meter integration."""

from datetime import timedelta

DOMAIN = "landisgyr_heat_meter"

GJ_TO_MWH = 0.277778  # conversion factor
ULTRAHEAT_TIMEOUT = 30  # reading the IR port can take some time
POLLING_INTERVAL = timedelta(days=1)  # Polling is only daily to prevent battery drain.
