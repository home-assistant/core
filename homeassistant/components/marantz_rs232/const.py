"""Constants for the Marantz RS-232 integration."""

import logging

from marantz_rs232 import MarantzV2007Receiver

from homeassistant.config_entries import ConfigEntry

LOGGER = logging.getLogger(__package__)
DOMAIN = "marantz_rs232"
DEFAULT_NAME = "Marantz receiver"

type MarantzRS232ConfigEntry = ConfigEntry[MarantzV2007Receiver]
