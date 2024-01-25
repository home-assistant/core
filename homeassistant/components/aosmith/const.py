"""Constants for the A. O. Smith integration."""

from datetime import timedelta

DOMAIN = "aosmith"

# Update interval to be used for normal background updates.
REGULAR_INTERVAL = timedelta(seconds=30)

# Update interval to be used while a mode or setpoint change is in progress.
FAST_INTERVAL = timedelta(seconds=1)

# Update interval to be used for energy usage data.
ENERGY_USAGE_INTERVAL = timedelta(minutes=10)
