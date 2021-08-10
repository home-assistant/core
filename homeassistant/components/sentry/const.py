"""Constants for the sentry integration."""

import logging

DOMAIN = "sentry"

CONF_DSN = "dsn"
CONF_ENVIRONMENT = "environment"
CONF_EVENT_CUSTOM_COMPONENTS = "event_custom_components"
CONF_EVENT_HANDLED = "event_handled"
CONF_EVENT_THIRD_PARTY_PACKAGES = "event_third_party_packages"
CONF_LOGGING_EVENT_LEVEL = "logging_event_level"
CONF_LOGGING_LEVEL = "logging_level"
CONF_TRACING = "tracing"
CONF_TRACING_SAMPLE_RATE = "tracing_sample_rate"

DEFAULT_LOGGING_EVENT_LEVEL = logging.ERROR
DEFAULT_LOGGING_LEVEL = logging.WARNING
DEFAULT_TRACING_SAMPLE_RATE = 1.0

LOGGING_LEVELS = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}

ENTITY_COMPONENTS = [
    "air_quality",
    "alarm_control_panel",
    "binary_sensor",
    "calendar",
    "camera",
    "climate",
    "cover",
    "device_tracker",
    "fan",
    "geo_location",
    "group",
    "humidifier",
    "light",
    "lock",
    "media_player",
    "remote",
    "scene",
    "sensor",
    "switch",
    "vacuum",
    "water_heater",
    "weather",
]
