"""The rest component schemas."""

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PARAMS,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template_entity import (
    TEMPLATE_ENTITY_BASE_SCHEMA,
    TEMPLATE_SENSOR_BASE_SCHEMA,
)
from homeassistant.util.ssl import SSLCipherList

from .const import (
    CONF_ENCODING,
    CONF_JSON_ATTRS,
    CONF_JSON_ATTRS_PATH,
    CONF_SSL_CIPHER_LIST,
    DEFAULT_ENCODING,
    DEFAULT_FORCE_UPDATE,
    DEFAULT_METHOD,
    DEFAULT_SSL_CIPHER_LIST,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    METHODS,
)
from .data import DEFAULT_TIMEOUT

RESOURCE_SCHEMA = {
    vol.Exclusive(CONF_RESOURCE, CONF_RESOURCE): cv.url,
    vol.Exclusive(CONF_RESOURCE_TEMPLATE, CONF_RESOURCE): cv.template,
    vol.Optional(CONF_AUTHENTICATION): vol.In(
        [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
    ),
    vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.template}),
    vol.Optional(CONF_PARAMS): vol.Schema({cv.string: cv.template}),
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(METHODS),
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PAYLOAD): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    vol.Optional(
        CONF_SSL_CIPHER_LIST,
        default=DEFAULT_SSL_CIPHER_LIST,
    ): vol.In([e.value for e in SSLCipherList]),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
}

SENSOR_SCHEMA = {
    **TEMPLATE_SENSOR_BASE_SCHEMA.schema,
    vol.Optional(CONF_JSON_ATTRS, default=[]): cv.ensure_list_csv,
    vol.Optional(CONF_JSON_ATTRS_PATH): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
}

BINARY_SENSOR_SCHEMA = {
    **TEMPLATE_ENTITY_BASE_SCHEMA.schema,
    vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
}


COMBINED_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        **RESOURCE_SCHEMA,
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(SENSOR_SCHEMA)]
        ),
        vol.Optional(BINARY_SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(BINARY_SENSOR_SCHEMA)]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            cv.remove_falsy,
            [COMBINED_SCHEMA],
        )
    },
    extra=vol.ALLOW_EXTRA,
)
