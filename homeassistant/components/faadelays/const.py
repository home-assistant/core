"""Constants for the FAA Delays integration."""

DOMAIN = "faadelays"

FAA_BINARY_SENSORS = {
    "GROUND_DELAY": ("Ground Delay", "mdi:airport"),
    "GROUND_STOP": ("Ground Stop", "mdi:airport"),
    "DEPART_DELAY": ("Departure Delay", "mdi:airplane-landing"),
    "ARRIVE_DELAY": ("Arrival Delay", "mdi:airplane-takeoff"),
    "CLOSURE": ("Closure", "mdi:airplane-off"),
}
