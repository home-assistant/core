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

from . import COMMAND_SCHEMA, DEFAULT_METHOD, DEFAULT_TIMEOUT, SUPPORT_REST_METHODS
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

AUTH_FIELDS = (CONF_AUTHENTICATION, CONF_USERNAME, CONF_PASSWORD)
ADVANCED_FIELDS = (
    CONF_HEADERS,
    CONF_CONTENT_TYPE,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
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
                probatio.Optional(CONF_VERIFY_SSL, default=True): BooleanSelector(),
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
RECONFIGURE_SCHEMA = probatio.Schema(COMMAND_FIELDS_SCHEMA)


def _flatten(user_input: dict[str, Any]) -> dict[str, Any]:
    """Move the values out of the form sections and drop empty values."""
    data = {**user_input, **user_input[SECTION_AUTH], **user_input[SECTION_ADVANCED]}
    del data[SECTION_AUTH], data[SECTION_ADVANCED]
    data.pop(CONF_ACTION, None)
    # An empty password is valid, servers may expect only a username
    return {
        key: value
        for key, value in data.items()
        if key == CONF_PASSWORD or value not in (None, "", {})
    }


def _to_sections(data: dict[str, Any]) -> dict[str, Any]:
    """Put stored values in the form sections, for suggested values."""
    return {
        **data,
        SECTION_AUTH: {key: data[key] for key in AUTH_FIELDS if key in data},
        SECTION_ADVANCED: {key: data[key] for key in ADVANCED_FIELDS if key in data},
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
        return self.async_create_entry(title="RESTful Command", data={})

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Create the entry with the commands imported from YAML."""
        return self.async_create_entry(
            title="RESTful Command",
            data={},
            subentries=import_data["subentries"],
        )

    @override
    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Start the flow for the first command after creating the entry."""
        if self.source != SOURCE_USER:
            return result
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
            elif any(
                subentry.unique_id == action
                for subentry in self._get_entry().subentries.values()
            ):
                errors[CONF_ACTION] = "action_exists"
            else:
                errors = _validate_command(data)
            if not errors:
                return self.async_create_entry(
                    title=name,
                    data={CONF_ACTION: action, **data},
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change a REST command, keeping its action name."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _flatten(user_input)
            errors = _validate_command(data)
            if not errors:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    data={CONF_ACTION: subentry.data[CONF_ACTION], **data},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA, user_input or _to_sections(dict(subentry.data))
            ),
            description_placeholders={
                **DESCRIPTION_PLACEHOLDERS,
                "action": f"{DOMAIN}.{subentry.data[CONF_ACTION]}",
            },
            errors=errors,
        )
