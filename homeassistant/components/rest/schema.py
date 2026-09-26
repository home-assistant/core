"""The rest component schemas."""

from codecs import lookup as codec_lookup
from typing import Any, override

import probatio

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASS_UNITS,
    DOMAIN as SENSOR_DOMAIN,
)
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
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    Platform,
    UnitOfTime,
)
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, selector
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
    CONF_JSON_ATTRS,
    CONF_JSON_ATTRS_PATH,
    CONF_PAYLOAD_TEMPLATE,
    CONF_SSL_CIPHER_LIST,
    CONF_SSL_SECTION,
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


class _TemplateURLSelector(selector.TemplateSelector):
    """Selector to validate templated urls."""

    @override
    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        template = cv.template(data)
        try:
            cv.url(template.async_render())
        except TemplateError as ex:
            raise probatio.Invalid(str(ex)) from ex
        return template.template


class _EncodingSelector(selector.TextSelector):
    """Selector to validate text encoding."""

    @override
    def __call__(self, data: Any) -> str | list[str]:
        encoding = str(super().__call__(data))
        try:
            codec_lookup(encoding)
        except LookupError:
            raise probatio.Invalid("codec not found") from None
        return encoding


class KeyedTemplateSelector(selector.ObjectSelector):
    """Object selector that supports unique key:Template inputs."""

    def __init__(self, translation_key: str) -> None:
        """Initialize the selector."""
        super().__init__(
            selector.ObjectSelectorConfig(
                fields={
                    "key": selector.ObjectSelectorField(
                        required=True, selector=selector.TextSelector()
                    ),
                    "value": selector.ObjectSelectorField(
                        required=True, selector=selector.TemplateSelector()
                    ),
                },
                multiple=True,
                label_field="key",
                description_field="value",
                translation_key=translation_key,
            )
        )

    @override
    def __call__(self, data: Any) -> Any:
        """Validate the selector then ensure there are not duplicate keys.

        The legacy configuration doesn't support duplicate keys even though
        they are supported for query params and headers in the http specifications.
        """
        super().__call__(data)
        keys: set[str] = set()
        for field in data:
            if field["key"] not in keys:
                keys.add(field["key"])
            else:
                raise probatio.Invalid(
                    f"Duplicate keys are not supported. Found multiple `{field['key']}` keys."
                )
        return data


class _auth_section(section):
    @override
    def __call__(self, data: Any) -> Any:
        try:
            return self.schema(data)
        except probatio.MultipleInvalid as ex:
            for error in ex.errors:
                if isinstance(error, probatio.InclusiveInvalid):
                    raise probatio.Invalid("credentials_missing") from error
            raise


def RESOURCE_FLOW_SCHEMA(collapse_auth: bool = True) -> probatio.Schema:
    """Resource flow schema with ability to collapse auth."""
    return probatio.Schema(
        {
            probatio.Required(CONF_RESOURCE): _TemplateURLSelector(),
            probatio.Required(
                CONF_METHOD, default=DEFAULT_METHOD
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=METHODS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    sort=True,
                )
            ),
            probatio.Required(CONF_AUTHENTICATION): _auth_section(
                probatio.Schema(
                    {
                        probatio.Required(
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
                        probatio.Inclusive(
                            CONF_USERNAME, CONF_AUTHENTICATION
                        ): selector.TextSelector(),
                        probatio.Inclusive(
                            CONF_PASSWORD, CONF_AUTHENTICATION
                        ): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.PASSWORD
                            )
                        ),
                    }
                ),
                options=SectionConfig(collapsed=collapse_auth),
            ),
            probatio.Optional(CONF_HEADERS): KeyedTemplateSelector(
                translation_key=CONF_HEADERS
            ),
            probatio.Optional(CONF_PARAMS): KeyedTemplateSelector(
                translation_key=CONF_PARAMS
            ),
            probatio.Optional(CONF_PAYLOAD): selector.TemplateSelector(),
            probatio.Required(CONF_SSL_SECTION): section(
                probatio.Schema(
                    {
                        probatio.Required(
                            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                        ): selector.BooleanSelector(),
                        probatio.Required(
                            CONF_SSL_CIPHER_LIST,
                            default=DEFAULT_SSL_CIPHER_LIST,
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    selector.SelectOptionDict(
                                        value=cipher.value,
                                        label=cipher.value.capitalize().replace(
                                            "_", " "
                                        ),
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
            probatio.Optional(
                CONF_TIMEOUT, default=DEFAULT_TIMEOUT
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.SECONDS,
                )
            ),
            probatio.Optional(
                CONF_ENCODING, default=DEFAULT_ENCODING
            ): _EncodingSelector(),
        }
    )


SUBENTRY_FLOW_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME): selector.TemplateSelector(),
        probatio.Optional(CONF_ICON): selector.TemplateSelector(),
        probatio.Optional(CONF_PICTURE): selector.TemplateSelector(),
        probatio.Optional(CONF_VALUE_TEMPLATE): selector.TemplateSelector(),
        probatio.Required(
            CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE
        ): selector.BooleanSelector(),
    }
)

_AVAILABILITY_SCHEMA = {
    probatio.Optional(CONF_AVAILABILITY): selector.TemplateSelector()
}

BINARY_SENSOR_SUBENTRY_FLOW_SCHEMA = SUBENTRY_FLOW_SCHEMA.extend(
    {
        probatio.Optional(CONF_DEVICE_CLASS): selector.DeviceClassSelector(
            selector.DeviceClassSelectorConfig(domain=Platform.BINARY_SENSOR)
        ),
    }
).extend(_AVAILABILITY_SCHEMA)

SENSOR_SUBENTRY_FLOW_SCHEMA = SUBENTRY_FLOW_SCHEMA.extend(
    {
        probatio.Optional(CONF_JSON_ATTRS_PATH): selector.TextSelector(),
        probatio.Optional(CONF_JSON_ATTRS, default=[]): selector.ObjectSelector(
            selector.ObjectSelectorConfig(
                multiple=True,
                fields={
                    "item": selector.ObjectSelectorField(
                        required=True, selector=selector.TextSelector()
                    )
                },
                translation_key=CONF_JSON_ATTRS,
            )
        ),
        probatio.Optional(CONF_UNIT_OF_MEASUREMENT): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(
                    {  # inner set removes duplicates
                        str(unit)
                        for units in DEVICE_CLASS_UNITS.values()
                        for unit in units
                        if unit is not None
                    }
                ),
                mode=selector.SelectSelectorMode.DROPDOWN,
                custom_value=True,
                sort=True,
                translation_key="sensor_unit_of_measurement",
            )
        ),
        probatio.Optional(CONF_DEVICE_CLASS): selector.DeviceClassSelector(
            selector.DeviceClassSelectorConfig(domain=Platform.SENSOR)
        ),
        probatio.Optional(CONF_STATE_CLASS): selector.StateClassSelector(
            selector.StateClassSelectorConfig()
        ),
    }
).extend(_AVAILABILITY_SCHEMA)
