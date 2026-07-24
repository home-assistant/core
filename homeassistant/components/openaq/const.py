"""Constants for the OpenAQ integration."""

import logging
from typing import Final

from openaq import (
    ApiKeyMissingError,
    ForbiddenError,
    HTTPRateLimitError,
    NotAuthorizedError,
    RateLimitError,
)
from openaq.core.exceptions import APIError

DOMAIN = "openaq"

LOGGER = logging.getLogger(__package__)

ATTRIBUTION: Final = "Data provided by OpenAQ"
CONF_LOCATION_ID: Final = "location_id"

MAX_RADIUS: Final = 25000
SUBENTRY_TYPE_LOCATION: Final = "location"

OPENAQ_AUTH_EXCEPTIONS: Final = (
    ApiKeyMissingError,
    ForbiddenError,
    NotAuthorizedError,
)
OPENAQ_RATE_LIMIT_EXCEPTIONS: Final = (HTTPRateLimitError, RateLimitError)
OPENAQ_API_EXCEPTIONS: Final = (APIError, OSError)
