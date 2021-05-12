"""Constants for the Mazda Connected Services integration."""

DOMAIN = "mazda"

DATA_CLIENT = "mazda_client"
DATA_COORDINATOR = "coordinator"

MAZDA_REGIONS = {"MNAO": "North America", "MME": "Europe", "MJO": "Japan"}

# Number of seconds to assume locked/unlocked state after making API call to lock/unlock the vehicle
LOCK_ASSUMED_STATE_PERIOD = 300
