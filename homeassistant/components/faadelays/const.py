"""Constants for the FAA Delays integration."""

DOMAIN = "faadelays"

FAA_BINARY_SENSORS = {
    "GROUND_DELAY": ("Ground Delay", "mdi:airport"),
    "GROUND_STOP": ("Ground Stop", "mdi:airport"),
    "DEPART_DELAY": ("Departure Delay", "mdi:airplane-takeoff"),
    "ARRIVE_DELAY": ("Arrival Delay", "mdi:airplane-landing"),
    "CLOSURE": ("Closure", "mdi:airplane-off"),
}
