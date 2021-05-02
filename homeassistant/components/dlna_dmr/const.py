"""Constants for the DLNA DMR component."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "dlna_dmr"

CONF_LISTEN_PORT = "listen_port"
CONF_CALLBACK_URL_OVERRIDE = "callback_url_override"
CONF_POLL_AVAILABILITY = "poll_availability"

CONNECT_TIMEOUT = 10
