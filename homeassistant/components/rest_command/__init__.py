"""Support for exposing regular REST commands as services."""

import probatio

from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_CONTENT_TYPE,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DOMAIN,
)
from .services import async_register_rest_command, async_setup_services

DEFAULT_TIMEOUT = 10
DEFAULT_METHOD = "get"
DEFAULT_VERIFY_SSL = True

SUPPORT_REST_METHODS = ["get", "patch", "post", "put", "delete"]


COMMAND_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): cv.template,
        probatio.Optional(CONF_METHOD, default=DEFAULT_METHOD): probatio.All(
            probatio.Lower, probatio.In(SUPPORT_REST_METHODS)
        ),
        probatio.Optional(CONF_HEADERS): probatio.Schema({cv.string: cv.template}),
        probatio.Optional(CONF_AUTHENTICATION): probatio.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        # A colon cannot be encoded into basic credentials, RFC 7617#section-2
        probatio.Inclusive(CONF_USERNAME, "authentication"): probatio.All(
            cv.string, probatio.Match(r"^[^:]*$")
        ),
        probatio.Inclusive(probatio.Secret(CONF_PASSWORD), "authentication"): cv.string,
        probatio.Optional(CONF_PAYLOAD): cv.template,
        probatio.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): probatio.Coerce(int),
        probatio.Optional(CONF_CONTENT_TYPE): cv.string,
        probatio.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        probatio.Optional(CONF_INSECURE_CIPHER, default=False): cv.boolean,
        probatio.Optional(CONF_SKIP_URL_ENCODING, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: cv.schema_with_slug_keys(COMMAND_SCHEMA)}, extra=probatio.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the REST command component."""
    for name, command_config in config[DOMAIN].items():
        async_register_rest_command(hass, name, command_config)

    async_setup_services(hass)

    return True
