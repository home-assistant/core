"""The rest component schemas."""

from codecs import lookup as codec_lookup
from typing import Any, override

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA as BINARY_SENSOR_DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASS_UNITS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
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


class _TemplateURLSelector(selector.TemplateSelector):
    """Selector to validate templated urls."""

    @override
    def __call__(self, data: Any) -> str:
        """Validate the passed selection."""
        template = cv.template(data)
        try:
            cv.url(template.async_render())
        except TemplateError as ex:
            raise vol.Invalid(str(ex)) from ex
        return template.template


class _EncodingSelector(selector.TextSelector):
    """Selector to validate text encoding."""

    @override
    def __call__(self, data: Any) -> str | list[str]:
        encoding = str(super().__call__(data))
        try:
            codec_lookup(encoding)
        except LookupError:
            raise vol.Invalid("codec not found") from None
        return encoding


class _ObjectSelector(selector.ObjectSelector):
    def __init__(self, translation_key: str) -> None:
        super().__init__(
            selector.ObjectSelectorConfig(
                fields={
                    "key": selector.ObjectSelectorField(
                        required=True, selector=selector.TemplateSelector()
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


class _auth_section(section):
    @override
    def __call__(self, data: Any) -> Any:
        try:
            return self.schema(data)
        except vol.MultipleInvalid as ex:
            for error in ex.errors:
                if isinstance(error, vol.InclusiveInvalid):
                    raise vol.Invalid("credentials_missing") from error
            raise


def RESOURCE_FLOW_SCHEMA(collapse_auth: bool = True) -> vol.Schema:
    """Resource flow schema with ability to collapse auth."""
    return vol.Schema(
        {
            vol.Required(CONF_RESOURCE): _TemplateURLSelector(),
            vol.Required(CONF_METHOD, default=DEFAULT_METHOD): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=METHODS, mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(CONF_AUTHENTICATION): _auth_section(
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
                        vol.Inclusive(
                            CONF_USERNAME, CONF_AUTHENTICATION
                        ): selector.TextSelector(),
                        vol.Inclusive(
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
            vol.Optional(CONF_HEADERS): _ObjectSelector(CONF_HEADERS),
            vol.Optional(CONF_PARAMS): _ObjectSelector(CONF_PARAMS),
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
            vol.Optional(
                CONF_TIMEOUT, default=DEFAULT_TIMEOUT
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.SECONDS,
                )
            ),
            vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): _EncodingSelector(),
        }
    )


SUBENTRY_FLOW_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): selector.TemplateSelector(),
        vol.Optional(CONF_ICON): selector.TemplateSelector(),
        vol.Optional(CONF_PICTURE): selector.TemplateSelector(),
        vol.Optional(CONF_VALUE_TEMPLATE): selector.TemplateSelector(),
        vol.Required(
            CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE
        ): selector.BooleanSelector(),
    }
)

_AVAILABILITY_SCHEMA = {vol.Optional(CONF_AVAILABILITY): selector.TemplateSelector()}

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
).extend(_AVAILABILITY_SCHEMA)

SENSOR_SUBENTRY_FLOW_SCHEMA = SUBENTRY_FLOW_SCHEMA.extend(
    {
        vol.Optional(CONF_JSON_ATTRS, default=[]): selector.ObjectSelector(
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
        vol.Optional(CONF_JSON_ATTRS_PATH): selector.TextSelector(),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    str(unit)
                    for units in DEVICE_CLASS_UNITS.values()
                    for unit in units
                    if unit is not None
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
                custom_value=True,
                sort=True,
            )
        ),
        vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[cls.value for cls in SensorDeviceClass],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="sensor_device_class",
                sort=True,
            ),
        ),
        vol.Optional(CONF_STATE_CLASS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[cls.value for cls in SensorStateClass],
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="sensor_state_class",
                sort=True,
            )
        ),
    }
).extend(_AVAILABILITY_SCHEMA)
