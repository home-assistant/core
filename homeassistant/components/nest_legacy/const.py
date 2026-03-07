"""Constants for the Nest Legacy integration."""

from __future__ import annotations

import logging
from typing import Final

LOGGER: logging.Logger = logging.getLogger(__package__)

DOMAIN: Final = "nest_legacy"
ATTRIBUTION: Final = "Data provided by Google/Nest"

CONF_ACCOUNT_TYPE: Final = "account_type"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_ISSUE_TOKEN: Final = "issue_token"
CONF_COOKIES: Final = "cookies"
CONF_FIELD_TEST: Final = "field_test"
CONF_EVENT_POLL_INTERVAL: Final = "event_poll_interval"

DEFAULT_EVENT_POLL_INTERVAL: Final = 5

# Protobuf enable options
CONF_ENABLE_PROTOBUF_LOCK: Final = "enable_protobuf_lock"
CONF_ENABLE_PROTOBUF_THERMOSTAT: Final = "enable_protobuf_thermostat"
CONF_ENABLE_PROTOBUF_STRUCTURE: Final = "enable_protobuf_structure"
CONF_ENABLE_PROTOBUF_PROTECT: Final = "enable_protobuf_protect"
CONF_ENABLE_PROTOBUF_CAMERA: Final = "enable_protobuf_camera"
