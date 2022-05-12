"""Constants for the Mazda Connected Services integration."""

DOMAIN = "mazda"

DATA_CLIENT = "mazda_client"
DATA_COORDINATOR = "coordinator"
DATA_VEHICLES = "vehicles"

MAZDA_REGIONS = {"MNAO": "North America", "MME": "Europe", "MJO": "Japan"}

SERVICES = [
    "send_poi",
    "start_charging",
    "start_engine",
    "stop_charging",
    "stop_engine",
    "turn_off_hazard_lights",
    "turn_on_hazard_lights",
]
