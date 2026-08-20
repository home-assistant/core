"""Config flow for RESTful Command."""

from typing import Any, override
from uuid import uuid4

import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    AUTHENTICATION_BEARER,
    AUTHENTICATION_NONE,
    CONF_CONTENT_TYPE,
    CONF_ENDPOINT_NAME,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DEFAULT_METHOD,
    DEFAULT_PAYLOAD,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SUPPORTED_REST_METHODS,
)

AUTHENTICATION_METHODS = [
    AUTHENTICATION_NONE,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    AUTHENTICATION_BEARER,
]

ENDPOINT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENDPOINT_NAME): TextSelector(),
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_METHOD, default=DEFAULT_METHOD): SelectSelector(
            SelectSelectorConfig(
                options=SUPPORTED_REST_METHODS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="method",
            )
        ),
        vol.Required(CONF_AUTHENTICATION, default=AUTHENTICATION_NONE): SelectSelector(
            SelectSelectorConfig(
                options=AUTHENTICATION_METHODS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="authentication",
            )
        ),
        vol.Optional(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
        ),
        vol.Optional(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
        vol.Optional(CONF_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_PAYLOAD, default=DEFAULT_PAYLOAD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
        ),
        vol.Optional(CONF_CONTENT_TYPE, default=CONTENT_TYPE_JSON): TextSelector(),
        vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): BooleanSelector(),
        vol.Required(CONF_INSECURE_CIPHER, default=False): BooleanSelector(),
        vol.Required(CONF_SKIP_URL_ENCODING, default=False): BooleanSelector(),
    }
)


def _validated_data(
    user_input: dict[str, Any], previous_data: dict[str, Any] | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate and normalize endpoint data."""
    errors: dict[str, str] = {}
    data = user_input.copy()
    data[CONF_ENDPOINT_NAME] = data[CONF_ENDPOINT_NAME].strip()
    if not data[CONF_ENDPOINT_NAME]:
        errors[CONF_ENDPOINT_NAME] = "required"

    try:
        parsed_url = URL(data[CONF_URL])
        port = parsed_url.port
        valid_url = (
            parsed_url.scheme in ("http", "https")
            and parsed_url.host is not None
            and (port is None or port <= 65535)
        )
    except TypeError, ValueError:
        valid_url = False
    if not valid_url:
        errors[CONF_URL] = "invalid_url"
    elif parsed_url.user is not None or parsed_url.password is not None:
        errors[CONF_URL] = "userinfo_not_allowed"

    authentication = data[CONF_AUTHENTICATION]
    if authentication in (
        HTTP_BASIC_AUTHENTICATION,
        HTTP_DIGEST_AUTHENTICATION,
    ):
        data.pop(CONF_TOKEN, None)
        if not data.get(CONF_USERNAME):
            errors[CONF_USERNAME] = "required"
        if not data.get(CONF_PASSWORD) and previous_data is not None:
            data[CONF_PASSWORD] = previous_data.get(CONF_PASSWORD, "")
        if not data.get(CONF_PASSWORD):
            errors[CONF_PASSWORD] = "required"
    elif authentication == AUTHENTICATION_BEARER:
        data.pop(CONF_USERNAME, None)
        data.pop(CONF_PASSWORD, None)
        if not data.get(CONF_TOKEN) and previous_data is not None:
            data[CONF_TOKEN] = previous_data.get(CONF_TOKEN, "")
        if not data.get(CONF_TOKEN):
            errors[CONF_TOKEN] = "required"
    else:
        data.pop(CONF_USERNAME, None)
        data.pop(CONF_PASSWORD, None)
        data.pop(CONF_TOKEN, None)

    data[CONF_TIMEOUT] = int(data[CONF_TIMEOUT])
    return data, errors


def _suggested_values(data: dict[str, Any]) -> dict[str, Any]:
    """Return form values without stored credentials."""
    suggested = dict(data)
    suggested.pop(CONF_PASSWORD, None)
    suggested.pop(CONF_TOKEN, None)
    return suggested


class RestCommandConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RESTful Command."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a UI-managed endpoint."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _validated_data(user_input)
            if not errors:
                self._async_abort_entries_match(
                    {
                        CONF_URL: data[CONF_URL],
                        CONF_METHOD: data[CONF_METHOD],
                    }
                )
                await self.async_set_unique_id(uuid4().hex)
                return self.async_create_entry(
                    title=data[CONF_ENDPOINT_NAME],
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                ENDPOINT_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure an endpoint."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _validated_data(user_input, dict(entry.data))
            if not errors:
                self._async_abort_entries_match(
                    {
                        CONF_URL: data[CONF_URL],
                        CONF_METHOD: data[CONF_METHOD],
                    }
                )
                return self.async_update_and_abort(
                    entry,
                    data=data,
                    title=data[CONF_ENDPOINT_NAME],
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                ENDPOINT_SCHEMA,
                user_input or _suggested_values(dict(entry.data)),
            ),
            errors=errors,
        )
