"""Constants for the MPRIS media playback remote control integration."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "hassmpris"
ENTRY_CLIENT = "client"
ENTRY_MANAGER = "manager"
ENTRY_PLAYERS = "players"
CONF_CLIENT_CERT = "client_cert"
CONF_CLIENT_KEY = "client_key"
CONF_TRUST_CHAIN = "trust_chain"

STEP_CONFIRM = "confirm"

ATTR_PLAYBACK_RATE = "playback_rate"
