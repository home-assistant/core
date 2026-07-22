"""Constants for the LG TV RS-232 integration."""

import logging

from lg_rs232_tv import LGTV

from homeassistant.config_entries import ConfigEntry

LOGGER = logging.getLogger(__package__)
DOMAIN = "lg_tv_rs232"

CONF_SET_ID = "set_id"

# TVState attributes the integration polls for; the TV is not asked for
# attributes the media player entity does not use.
QUERY_ATTRIBUTES = ("power", "input_source", "volume", "volume_mute", "balance")

type LGTVRS232ConfigEntry = ConfigEntry[LGTV]
