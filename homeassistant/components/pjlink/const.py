"""Const for PJLink."""

import logging

INTEGRATION_NAME = "PJLink"
DOMAIN = "pjlink"

CONF_ENCODING = "encoding"

DEFAULT_PORT = 4352
DEFAULT_ENCODING = "utf-8"
DEFAULT_TIMEOUT = 10

UPDATE_INTERVAL = 10

ERROR_KEYS = [
    ("fan", "Fan Error"),
    ("lamp", "Lamp Error"),
    ("temp", "Temperature Error"),
    ("cover", "Cover Error"),
    ("filter", "Filter Error"),
    ("other", "Other Error"),
]

ATTR_IS_WARNING = "is_warning"
ATTR_PROJECTOR_STATUS = "projector_status"
ATTR_OTHER_INFO = "other_info"

ATTR_TO_PROPERTY = [
    ATTR_PROJECTOR_STATUS,
    ATTR_OTHER_INFO,
]

_LOGGER = logging.getLogger(__package__)
