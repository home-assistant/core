"""Constants for the huum integration."""

from aiohttp import ContentTypeError
from huum.exceptions import Forbidden, NotAuthenticated

from homeassistant.const import Platform

DOMAIN = "huum"

# The Huum API responds with an HTTP 200 and an HTML page instead of a 401 or
# 403 when the credentials are invalid, so aiohttp raises ContentTypeError
# when decoding the response as JSON.
AUTH_ERRORS = (Forbidden, NotAuthenticated, ContentTypeError)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
]

CONFIG_STEAMER = 1
CONFIG_LIGHT = 2
CONFIG_STEAMER_AND_LIGHT = 3

CONFIG_DEFAULT_MIN_TEMP = 40
CONFIG_DEFAULT_MAX_TEMP = 110
