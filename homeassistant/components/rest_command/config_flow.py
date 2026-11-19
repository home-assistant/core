"""Config flow for the REST command integration."""

from typing import Any, override

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
)
from .const import (
    CONF_ACTION,
    CONF_CONTENT_TYPE,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DOMAIN,
    SECTION_ADVANCED,
    SECTION_AUTH,
    SUBENTRY_TYPE_COMMAND,
)

COMMAND_FIELDS_SCHEMA = {
    probatio.Required(CONF_URL): TemplateSelector(),
    probatio.Required(CONF_METHOD, default=DEFAULT_METHOD): SelectSelector(
        SelectSelectorConfig(
            options=SUPPORT_REST_METHODS,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=CONF_METHOD,
        )
    ),
    probatio.Optional(CONF_PAYLOAD): TemplateSelector(),
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
    probatio.Required(SECTION_ADVANCED): section(
        probatio.Schema(
            {
                probatio.Optional(CONF_HEADERS): ObjectSelector(),
                probatio.Optional(CONF_CONTENT_TYPE): TextSelector(),
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
    "example_url": "http://192.168.1.10/api/door/{{ door }}",
    "example_payload": '{"state": "{{ state }}"}',
    "example_data": "door: front",
    "example_headers": 'Authorization: "Bearer {{ token }}"',
}

TITLE = "RESTful Command"


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    """Move the values out of the form sections and drop empty values."""
    data = {**user_input, **user_input[SECTION_AUTH], **user_input[SECTION_ADVANCED]}
    del data[SECTION_AUTH], data[SECTION_ADVANCED]
    data.pop(CONF_ACTION, None)
    # An empty username or password is valid, like in YAML: some servers
    # expect only a username, others only a token as the password
    return {
        key: value
        for key, value in data.items()
        if value not in (None, "", {})
        or (key in (CONF_USERNAME, CONF_PASSWORD) and value == "")
    }


def _validate_command(data: dict[str, Any]) -> dict[str, str]:
    """Validate a command and return the form errors."""
    try:
        COMMAND_SCHEMA(data)
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
        """Create the entry that holds the commands."""
        return self.async_create_entry(title=TITLE, data={})

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
        errors: dict[str, str] = {}
        placeholders = {**DESCRIPTION_PLACEHOLDERS, "action": ""}
        if user_input is not None:
            data = _flatten(user_input)
            name: str = user_input[CONF_ACTION].strip()
            action = slugify(name)
            placeholders["action"] = f"{DOMAIN}.{action}"
            if action in ("", "unknown", SERVICE_RELOAD):
                errors[CONF_ACTION] = "invalid_action"
            elif self.hass.services.has_service(DOMAIN, action) or any(
                subentry.unique_id == action
                for subentry in self._get_entry().subentries.values()
            ):
                errors[CONF_ACTION] = "action_exists"
            else:
                errors = _validate_command(data)
            if not errors:
                return self.async_create_entry(
                    title=name,
                    data=data,
                    unique_id=action,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input or {}
            ),
            description_placeholders=placeholders,
            errors=errors,
        )
