"""Constants for the zeversolar integration."""

from homeassistant.const import Platform

DOMAIN = "zeversolar"

PLATFORMS = [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]

# Power limit ramp settings.
# The inverter does not implement its own internal ramp — changes take effect
# immediately. Stepping in 10% increments with pauses avoids abrupt power
# transitions that can cause voltage fluctuations on the local grid.
# Intervals are conservative by design; there is no empirical breaking point.
MINIMUM_LIMIT = 5  # % — never ramp below this
STEP_SIZE = 10  # % per ramp step
STEP_INTERVAL_DOWN = 20  # seconds between steps when ramping down (slower = safer)
STEP_INTERVAL_UP = 10  # seconds between steps when ramping up
HTTP_TIMEOUT = 5  # seconds
