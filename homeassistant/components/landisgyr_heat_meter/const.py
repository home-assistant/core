"""Constants for the Landis+Gyr Heat Meter integration."""

from datetime import timedelta

DOMAIN = "landisgyr_heat_meter"

CONF_BATTERY_POWERED = "battery_powered"

ULTRAHEAT_TIMEOUT = 30  # reading the IR port can take some time
POLLING_INTERVAL_BATTERY = timedelta(
    days=1
)  # Polling is only daily to prevent battery drain.
POLLING_INTERVAL_MAINS = timedelta(hours=1)
