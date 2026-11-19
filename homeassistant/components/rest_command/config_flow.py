"""Config flow for the REST command integration."""

from typing import Any, override
from urllib.parse import urlparse

import probatio

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    FlowType,
    SubentryFlowContext,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    SERVICE_RELOAD,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from . import (
    COMMAND_SCHEMA,
    DEFAULT_METHOD,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    SUPPORT_REST_METHODS,
    flatten,
    merge_command_config,
)
from .const import (
    CONF_ACTION,
    CONF_CONTENT_TYPE,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DOMAIN,
    SECTION_ADDITIONAL,
    SECTION_AUTH,
    SUBENTRY_TYPE_COMMAND,
)

SERVER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        probatio.Required(SECTION_AUTH): section(
            probatio.Schema(
                {
                    probatio.Optional(CONF_AUTHENTICATION): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                HTTP_BASIC_AUTHENTICATION,
                                HTTP_DIGEST_AUTHENTICATION,
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key=CONF_AUTHENTICATION,
                        )
                    ),
                    probatio.Optional(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT, autocomplete="username"
                        )
                    ),
                    probatio.Optional(probatio.Secret(CONF_PASSWORD)): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                }
            ),
            SectionConfig(collapsed=True),
        ),
        probatio.Required(SECTION_ADDITIONAL): section(
            probatio.Schema(
                {
                    probatio.Optional(CONF_HEADERS): ObjectSelector(),
                    probatio.Optional(
                        CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                    probatio.Optional(
                        CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
                    ): BooleanSelector(),
                    probatio.Optional(
                        CONF_INSECURE_CIPHER, default=False
                    ): BooleanSelector(),
                }
            ),
            SectionConfig(collapsed=True),
        ),
    }
)

COMMAND_FIELDS_SCHEMA = {
    probatio.Optional(CONF_PATH): TemplateSelector(),
    probatio.Required(CONF_METHOD, default=DEFAULT_METHOD): SelectSelector(
        SelectSelectorConfig(
            options=SUPPORT_REST_METHODS,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=CONF_METHOD,
        )
    ),
    probatio.Optional(CONF_PAYLOAD): TemplateSelector(),
    probatio.Required(SECTION_ADDITIONAL): section(
        probatio.Schema(
            {
                probatio.Optional(CONF_CONTENT_TYPE): TextSelector(),
                probatio.Optional(CONF_HEADERS): ObjectSelector(),
                probatio.Optional(
                    CONF_SKIP_URL_ENCODING, default=False
                ): BooleanSelector(),
            }
        ),
        SectionConfig(collapsed=True),
    ),
}

USER_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_ACTION): TextSelector(), **COMMAND_FIELDS_SCHEMA}
)

# Shown in the form texts; braces cannot be used in translations directly
DESCRIPTION_PLACEHOLDERS = {
    "example_url": "http://192.168.1.10",
    "example_path": "/api/door/{{ door }}",
    "example_payload": '{"state": "{{ state }}"}',
    "example_data": "door: front",
    "example_headers": 'Authorization: "Bearer {{ token }}"',
}


def _is_server_url(url: str) -> bool:
    """Return if the URL is an http(s) address that a path can be added to."""
    try:
        cv.url(url)
    except probatio.Invalid, ValueError:
        return False
    parsed = urlparse(url)
    # Credentials belong in the authentication section, not in the entry title
    return not (parsed.query or parsed.fragment or "@" in parsed.netloc)


def _validate(
    server: dict[str, Any], command: dict[str, Any] | None = None
) -> dict[str, str]:
    """Validate a server, or one of its commands, and return the form errors."""
    if not all(
        isinstance(flatten(data).get(CONF_HEADERS, {}), dict)
        for data in (server, command or {})
    ):
        return {"base": "invalid_command"}
    config = merge_command_config(server, command or {})
    config.pop(CONF_ACTION, None)
    try:
        COMMAND_SCHEMA(config)
    except probatio.Invalid:
        return {"base": "invalid_command"}
    return {}


class RestCommandConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for REST commands."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentries supported by this handler."""
        return {SUBENTRY_TYPE_COMMAND: RestCommandSubentryFlowHandler}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a server that commands are sent to."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # The path of each command starts with a slash
            url = user_input[CONF_URL] = user_input[CONF_URL].strip().rstrip("/")
            self._async_abort_entries_match({CONF_URL: url})
            if not _is_server_url(url):
                errors[CONF_URL] = "invalid_url"
            else:
                errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title=url, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                SERVER_SCHEMA, user_input or {}
            ),
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
            errors=errors,
        )

    @override
    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Start the flow for the first command after creating the entry."""
        subentry_result = await self.hass.config_entries.subentries.async_init(
            (result["result"].entry_id, SUBENTRY_TYPE_COMMAND),
            context=SubentryFlowContext(source=SOURCE_USER),
        )
        result["next_flow"] = (
            FlowType.CONFIG_SUBENTRIES_FLOW,
            subentry_result["flow_id"],
        )
        return result


class RestCommandSubentryFlowHandler(ConfigSubentryFlow):
    """Flow to add or change a REST command."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a REST command."""
        entry = self._get_entry()
        errors: dict[str, str] = {}
        placeholders = {
            **DESCRIPTION_PLACEHOLDERS,
            "action": "",
            "url": entry.data[CONF_URL],
        }
        if user_input is not None:
            path = user_input.get(CONF_PATH, "")
            if path and not path.startswith("/"):
                user_input[CONF_PATH] = f"/{path}"
            action = user_input[CONF_ACTION] = user_input[CONF_ACTION].strip()
            placeholders["action"] = f"{DOMAIN}.{action}"
            # The action name is used as written, so it must already be a slug
            if action in ("", "unknown", SERVICE_RELOAD) or action != slugify(action):
                errors[CONF_ACTION] = "invalid_action"
            elif self.hass.services.has_service(DOMAIN, action) or any(
                subentry.data[CONF_ACTION] == action
                for other in self.hass.config_entries.async_entries(DOMAIN)
                for subentry in other.subentries.values()
            ):
                errors[CONF_ACTION] = "action_exists"
            else:
                errors = _validate(dict(entry.data), user_input)
            if not errors:
                return self.async_create_entry(title=action, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input or {}
            ),
            description_placeholders=placeholders,
            errors=errors,
        )
