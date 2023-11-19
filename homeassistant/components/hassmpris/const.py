"""Constants for the MPRIS media playback remote control integration."""

import logging
from typing import Final

from homeassistant.const import CONF_HOST as _CONF_HOST

LOGGER = logging.getLogger(__package__)

DOMAIN = "hassmpris"

CONF_HOST: Final = _CONF_HOST
CONF_CAKES_PORT: Final = "cakes_port"
CONF_CLIENT_CERT: Final = "client_cert"
CONF_CLIENT_KEY: Final = "client_key"
CONF_MPRIS_PORT: Final = "mpris_port"
CONF_UNIQUE_ID: Final = "unique_id"
CONF_TRUST_CHAIN: Final = "trust_chain"

DEF_CAKES_PORT = 40052
DEF_HOST = "localhost"
DEF_MPRIS_PORT = 40051

EXPECTED_HEARTBEAT_FREQUENCY: Final = 10

STEP_CONFIRM = "confirm"
STEP_REAUTH_CONFIRM = "reauth_confirm"
STEP_USER = "user"
STEP_ZEROCONF_CONFIRM = "zeroconf_confirm"

REASON_CANNOT_CONNECT = "cannot_connect"
REASON_CANNOT_DECRYPT = "cannot_decrypt"
REASON_IGNORED = "ignored"
REASON_REJECTED = "rejected"
REASON_INVALID_ZEROCONF = "invalid_zeroconf"
REASON_TIMEOUT = "timeout_connect"

ATTR_PLAYBACK_RATE = "playback_rate"
