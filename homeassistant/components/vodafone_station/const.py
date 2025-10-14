"""Vodafone Station constants."""

import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "vodafone_station"
SCAN_INTERVAL = 30

CONF_DEVICE_DETAILS = "device_details"
DEVICE_URL = "device_url"
DEVICE_TYPE = "device_type"

DEFAULT_DEVICE_NAME = "Unknown device"
DEFAULT_HOST = "192.168.1.1"
DEFAULT_USERNAME = "vodafone"

LINE_TYPES = ["dsl", "fiber", "internet_key"]
