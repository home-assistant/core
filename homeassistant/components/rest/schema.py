"""The rest component schemas."""

import probatio

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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    TEMPLATE_ENTITY_BASE_SCHEMA,
    TEMPLATE_SENSOR_BASE_SCHEMA,
    ValueTemplate,
)
from homeassistant.util.ssl import SSLCipherList

from .const import (
    CONF_ENCODING,
    CONF_JSON_ATTRS,
    CONF_JSON_ATTRS_PATH,
    CONF_PAYLOAD_TEMPLATE,
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
    probatio.Exclusive(CONF_RESOURCE, CONF_RESOURCE): cv.url,
    probatio.Exclusive(CONF_RESOURCE_TEMPLATE, CONF_RESOURCE): cv.template,
    probatio.Optional(CONF_AUTHENTICATION): probatio.In(
        [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
    ),
    probatio.Optional(CONF_HEADERS): probatio.Schema({cv.string: cv.template}),
    probatio.Optional(CONF_PARAMS): probatio.Schema({cv.string: cv.template}),
    probatio.Optional(CONF_METHOD, default=DEFAULT_METHOD): probatio.In(METHODS),
    probatio.Optional(CONF_USERNAME): cv.string,
    probatio.Optional(CONF_PASSWORD): cv.string,
    probatio.Exclusive(CONF_PAYLOAD, CONF_PAYLOAD): cv.string,
    probatio.Exclusive(CONF_PAYLOAD_TEMPLATE, CONF_PAYLOAD): cv.template,
    probatio.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    probatio.Optional(
        CONF_SSL_CIPHER_LIST,
        default=DEFAULT_SSL_CIPHER_LIST,
    ): probatio.In([e.value for e in SSLCipherList]),
    probatio.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    probatio.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
}

SENSOR_SCHEMA = {
    **TEMPLATE_SENSOR_BASE_SCHEMA.schema,
    probatio.Optional(CONF_JSON_ATTRS, default=[]): cv.ensure_list_csv,
    probatio.Optional(CONF_JSON_ATTRS_PATH): cv.string,
    probatio.Optional(CONF_VALUE_TEMPLATE): probatio.All(
        cv.template, ValueTemplate.from_template
    ),
    probatio.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    probatio.Optional(CONF_AVAILABILITY): cv.template,
}

BINARY_SENSOR_SCHEMA = {
    **TEMPLATE_ENTITY_BASE_SCHEMA.schema,
    probatio.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    probatio.Optional(CONF_VALUE_TEMPLATE): probatio.All(
        cv.template, ValueTemplate.from_template
    ),
    probatio.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    probatio.Optional(CONF_AVAILABILITY): cv.template,
}


COMBINED_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        **RESOURCE_SCHEMA,
        probatio.Optional(SENSOR_DOMAIN): probatio.All(
            cv.ensure_list, [probatio.Schema(SENSOR_SCHEMA)]
        ),
        probatio.Optional(BINARY_SENSOR_DOMAIN): probatio.All(
            cv.ensure_list, [probatio.Schema(BINARY_SENSOR_SCHEMA)]
        ),
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.All(
            cv.ensure_list,
            cv.remove_falsy,
            [COMBINED_SCHEMA],
        )
    },
    extra=probatio.ALLOW_EXTRA,
)
