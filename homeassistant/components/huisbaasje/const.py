"""Constants for the Huisbaasje integration."""
from homeassistant.const import VOLUME_CUBIC_METERS, TIME_HOURS


DOMAIN = "huisbaasje"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

FLOW_CUBIC_METERS_PER_HOUR = f"{VOLUME_CUBIC_METERS}/{TIME_HOURS}"

SOURCE_TYPES = [
    "electricity",
    "electricityIn",
    "electricityInLow",
    "electricityOut",
    "electricityOutLow",
    "electricityExpected",
    "electricityGoal",
    "gas",
    "gasExpected",
    "gasGoal",
]


POLLING_INTERVAL = 5
"""Interval in seconds between polls to huisbaasje"""
