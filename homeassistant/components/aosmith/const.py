"""Constants for the A. O. Smith integration."""

from datetime import timedelta

DOMAIN = "aosmith"

AOSMITH_MODE_ELECTRIC = "ELECTRIC"
AOSMITH_MODE_HEAT_PUMP = "HEAT_PUMP"
AOSMITH_MODE_HYBRID = "HYBRID"
AOSMITH_MODE_VACATION = "VACATION"

# Update interval to be used for normal background updates.
REGULAR_INTERVAL = timedelta(seconds=30)

# Update interval to be used while a mode or setpoint change is in progress.
FAST_INTERVAL = timedelta(seconds=1)

# Update interval to be used for energy usage data.
ENERGY_USAGE_INTERVAL = timedelta(minutes=10)

HOT_WATER_STATUS_MAP = {
    "LOW": "low",
    "MEDIUM": "medium",
    "HIGH": "high",
}
