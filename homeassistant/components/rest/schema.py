"""The rest component schemas."""

from codecs import lookup as codec_lookup
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_HEADERS,
    CONF_ICON,
    CONF_METHOD,
    CONF_NAME,
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
    UnitOfTime,
)
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    TEMPLATE_ENTITY_BASE_SCHEMA,
    TEMPLATE_SENSOR_BASE_SCHEMA,
    ValueTemplate,
)
from homeassistant.util.ssl import SSLCipherList

from .const import (
    CONF_ENCODING,
    CONF_INITIAL_SUBENTRY_TYPE,
    CONF_JSON_ATTRS,
    CONF_JSON_ATTRS_PATH,
    CONF_PAYLOAD_TEMPLATE,
    CONF_SSL_CIPHER_LIST,
    CONF_SSL_SECTION,
    CONFIG_ENTRY_PLATFORMS,
    DEFAULT_ENCODING,
    DEFAULT_FORCE_UPDATE,
    DEFAULT_METHOD,
    DEFAULT_SSL_CIPHER_LIST,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    METHODS,
    MIN_SCAN_INTERVAL,
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
    vol.Exclusive(CONF_PAYLOAD, CONF_PAYLOAD): cv.string,
    vol.Exclusive(CONF_PAYLOAD_TEMPLATE, CONF_PAYLOAD): cv.template,
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
    vol.Optional(CONF_VALUE_TEMPLATE): vol.All(
        cv.template, ValueTemplate.from_template
    ),
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    vol.Optional(CONF_AVAILABILITY): cv.template,
}

BINARY_SENSOR_SCHEMA = {
    **TEMPLATE_ENTITY_BASE_SCHEMA.schema,
    vol.Optional(CONF_DEVICE_CLASS): BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_VALUE_TEMPLATE): vol.All(
        cv.template, ValueTemplate.from_template
    ),
    vol.Optional(CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE): cv.boolean,
    vol.Optional(CONF_AVAILABILITY): cv.template,
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

RESOURCE_FLOW_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_RESOURCE): selector.TemplateSelector(),
        vol.Required(CONF_METHOD, default=DEFAULT_METHOD): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=METHODS, mode=selector.SelectSelectorMode.DROPDOWN
            )
        ),
        vol.Required(CONF_AUTHENTICATION): section(
            vol.Schema(
                {
                    vol.Required(
                        CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                HTTP_BASIC_AUTHENTICATION,
                                HTTP_DIGEST_AUTHENTICATION,
                            ],
                            translation_key=CONF_AUTHENTICATION,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(CONF_USERNAME): selector.TextSelector(),
                    vol.Optional(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            options=SectionConfig(collapsed=True),
        ),
        vol.Optional(CONF_HEADERS): selector.ObjectSelector(),
        vol.Optional(CONF_PARAMS): selector.ObjectSelector(),
        vol.Optional(CONF_PAYLOAD): selector.TemplateSelector(),
        vol.Required(CONF_SSL_SECTION): section(
            vol.Schema(
                {
                    vol.Required(
                        CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                    ): selector.BooleanSelector(),
                    vol.Required(
                        CONF_SSL_CIPHER_LIST,
                        default=DEFAULT_SSL_CIPHER_LIST,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=cipher.value,
                                    label=cipher.value.capitalize().replace("_", " "),
                                )
                                for cipher in SSLCipherList
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            options=SectionConfig(collapsed=True),
        ),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): selector.TextSelector(),
    }
)


def _template_url(value: Any) -> Template:
    template = cv.template(value)
    try:
        cv.url(template.async_render(parse_result=False))
    except TemplateError as ex:
        raise vol.Invalid(str(ex), error_type="template error") from None
    return template


def _valid_codec(value: Any) -> Any:
    try:
        codec_lookup(value)
    except LookupError:
        raise vol.Invalid("codec not found") from None
    return value


RESOURCE_VALIDATION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_RESOURCE): _template_url,
        vol.Required(CONF_METHOD): cv.string,
        vol.Required(CONF_AUTHENTICATION): vol.Schema(
            {
                vol.Required(CONF_AUTHENTICATION): cv.string,
                vol.Inclusive(
                    CONF_USERNAME, CONF_AUTHENTICATION, msg="credentials_missing"
                ): cv.string,
                vol.Inclusive(
                    CONF_PASSWORD, CONF_AUTHENTICATION, msg="credentials_missing"
                ): cv.string,
            },
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.template: cv.template}),
        vol.Optional(CONF_PARAMS): vol.Schema({cv.template: cv.template}),
        vol.Optional(CONF_PAYLOAD): cv.template,
        vol.Required(CONF_SSL_SECTION): vol.Schema(
            {
                vol.Required(CONF_VERIFY_SSL): cv.boolean,
                vol.Required(CONF_SSL_CIPHER_LIST): vol.In(SSLCipherList),
            }
        ),
        vol.Optional(CONF_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_ENCODING): _valid_codec,
    }
)

OPTIONS_FLOW_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_SCAN_INTERVAL,
                mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        )
    }
)

CREATE_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_INITIAL_SUBENTRY_TYPE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=CONFIG_ENTRY_PLATFORMS,
                sort=True,
                translation_key="entity_platforms",
            )
        )
    }
)

SUBENTRY_FLOW_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): selector.TemplateSelector(),
        vol.Optional(CONF_ICON): selector.TemplateSelector(),
        vol.Optional(CONF_PICTURE): selector.TemplateSelector(),
        vol.Optional(CONF_VALUE_TEMPLATE): selector.TemplateSelector(),
        vol.Optional(
            CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE
        ): selector.BooleanSelector(),
    }
)

_AVAILABILTY_SCHEMA = {vol.Optional(CONF_AVAILABILITY): selector.TemplateSelector()}

BINARY_SENSOR_SUBENTRY_FLOW_SCHEMA = SUBENTRY_FLOW_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[cls.value for cls in BinarySensorDeviceClass],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="binary_sensor_device_class",
                sort=True,
            ),
        ),
    }
).extend(_AVAILABILTY_SCHEMA)
