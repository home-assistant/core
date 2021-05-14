"""Constants for the FAA Delays integration."""

from homeassistant.const import ATTR_ICON, ATTR_NAME

DOMAIN = "faa_delays"

FAA_BINARY_SENSORS = {
    "GROUND_DELAY": {
        ATTR_NAME: "Ground Delay",
        ATTR_ICON: "mdi:airport",
    },
    "GROUND_STOP": {
        ATTR_NAME: "Ground Stop",
        ATTR_ICON: "mdi:airport",
    },
    "DEPART_DELAY": {
        ATTR_NAME: "Departure Delay",
        ATTR_ICON: "mdi:airplane-takeoff",
    },
    "ARRIVE_DELAY": {
        ATTR_NAME: "Arrival Delay",
        ATTR_ICON: "mdi:airplane-landing",
    },
    "CLOSURE": {
        ATTR_NAME: "Closure",
        ATTR_ICON: "mdi:airplane:off",
    },
}
