"""Const for conversation integration."""

DOMAIN = "conversation"

DEFAULT_EXPOSED_DOMAINS = {
    "binary_sensor",
    "climate",
    "cover",
    "fan",
    "humidifier",
    "light",
    "lock",
    "scene",
    "script",
    "sensor",
    "switch",
    "vacuum",
    "water_heater",
}

DEFAULT_EXPOSED_ATTRIBUTES = {"device_class"}
