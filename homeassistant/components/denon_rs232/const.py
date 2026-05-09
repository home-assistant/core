"""Constants for the Denon RS232 integration."""

import logging

from denon_rs232 import DenonReceiver

from homeassistant.config_entries import ConfigEntry

LOGGER = logging.getLogger(__package__)
DOMAIN = "denon_rs232"

type DenonRS232ConfigEntry = ConfigEntry[DenonReceiver]
