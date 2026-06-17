"""Constants for the Marantz RS-232 integration."""

import logging

from marantz_rs232 import (
    MarantzV2003Receiver,
    MarantzV2007Receiver,
    MarantzV2015Receiver,
)

from homeassistant.config_entries import ConfigEntry

LOGGER = logging.getLogger(__package__)
DOMAIN = "marantz_rs232"

type MarantzReceiver = (
    MarantzV2015Receiver | MarantzV2007Receiver | MarantzV2003Receiver
)
type MarantzRS232ConfigEntry = ConfigEntry[MarantzReceiver]
