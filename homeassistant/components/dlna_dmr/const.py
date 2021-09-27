"""Constants for the DLNA DMR component."""

import logging
from typing import Final

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "dlna_dmr"

CONF_LISTEN_PORT: Final = "listen_port"
CONF_CALLBACK_URL_OVERRIDE: Final = "callback_url_override"
CONF_POLL_AVAILABILITY: Final = "poll_availability"

DEFAULT_NAME: Final = "DLNA Digital Media Renderer"

CONNECT_TIMEOUT: Final = 10
