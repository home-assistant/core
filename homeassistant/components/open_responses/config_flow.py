"""Config flow for Open Responses integration."""

from collections.abc import Mapping
from typing import Any

from openresponses.client import AsyncOpenResponsesClient
from openresponses.exceptions import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    ModelError,
    OpenResponsesError,
    RateLimitError,
)
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TemplateSelector,
)
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_BASE_URL,
    CONF_GENERATED_DEFAULT_SUBENTRY,
    CONF_MAX_OUTPUT_TOKENS,
    CONF_PROMPT,
    CONF_STORE_RESPONSES,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_MAX_OUTPUT_TOKENS,
    RECOMMENDED_STORE_RESPONSES,
)
from .helpers import client_base_url

VALIDATION_TIMEOUT = 10.0
STREAM_FAILURE_EVENTS = {
    "error",
    "response.error",
    "response.failed",
    "response.incomplete",
}

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_BASE_URL): vol.All(
            str, str.strip, cv.url, lambda value: value.rstrip("/")
        ),
        vol.Required(CONF_MODEL): str,
    }
)


class OpenResponsesStreamValidationError(Exception):
    """Raised when streaming validation reports a failed response."""


def _is_default_subentry(subentry: ConfigSubentry) -> bool:
    """Return whether a subentry is the generated default subentry."""
    return subentry.data.get(CONF_GENERATED_DEFAULT_SUBENTRY) is True


def _entry_matches_auth(entry: ConfigEntry, data: dict[str, Any]) -> bool:
    """Return whether a config entry uses the same auth endpoint."""
    return entry.data.get(CONF_API_KEY) == data[CONF_API_KEY] and client_base_url(
        entry.data.get(CONF_BASE_URL, "")
    ) == client_base_url(data[CONF_BASE_URL])


def _stream_event_to_dict(event: Any) -> dict[str, Any]:
    """Convert stream events to Open Responses event dictionaries."""
    if isinstance(event, dict):
        return event
    if hasattr(event, "event") and hasattr(event, "data"):
        data = event.data.copy()
        data.setdefault("type", event.event)
        return data
    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json", exclude_none=True)
    if hasattr(event, "to_dict"):
        return event.to_dict()
    return {}


def _stream_validation_failed(event: dict[str, Any]) -> bool:
    """Return whether a validation stream event should fail setup."""
    event_type = event.get("type")
    if event_type == "response.incomplete":
        response = event.get("response")
        incomplete_details = (
            response.get("incomplete_details") if isinstance(response, dict) else None
        )
        if (
            isinstance(incomplete_details, dict)
            and incomplete_details.get("reason") == "max_output_tokens"
        ):
            return False

    return event_type in STREAM_FAILURE_EVENTS


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate Open Responses connection details."""
    client = AsyncOpenResponsesClient(
        api_key=data[CONF_API_KEY],
        base_url=client_base_url(data[CONF_BASE_URL]),
        http_client=get_async_client(hass),
    )
    ping_input = [{"type": "message", "role": "user", "content": "ping"}]

    await client.create(
        model=data[CONF_MODEL],
        input=ping_input,
        max_output_tokens=16,
        store=False,
        timeout=VALIDATION_TIMEOUT,
    )
    stream = await client.create(
        model=data[CONF_MODEL],
        input=ping_input,
        max_output_tokens=16,
        store=False,
        stream=True,
        timeout=VALIDATION_TIMEOUT,
    )
    async for raw_event in stream:
        event = _stream_event_to_dict(raw_event)
        if _stream_validation_failed(event):
            raise OpenResponsesStreamValidationError


def _error_mentions_model(err: BadRequestError) -> bool:
    """Return whether an API error points at the requested model."""
    error = (
        err.response_body.get("error") if isinstance(err.response_body, dict) else None
    )
    if not isinstance(error, dict):
        return False

    return any(
        "model" in str(error.get(key, "")).lower()
        for key in ("code", "param", "message")
    )


def _async_update_default_subentry_models(
    hass: HomeAssistant, entry: ConfigEntry, model: str
) -> None:
    """Update generated default subentries when reauth changes the model."""
    old_model = entry.data[CONF_MODEL]

    for subentry in entry.subentries.values():
        if subentry.data.get(CONF_MODEL) != old_model or not _is_default_subentry(
            subentry
        ):
            continue

        hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data={**subentry.data, CONF_MODEL: model},
        )


class OpenResponsesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Open Responses."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            if self.source == SOURCE_REAUTH:
                reauth_entry = self._get_reauth_entry()
                for entry in self._async_current_entries(include_ignore=False):
                    if entry.entry_id != reauth_entry.entry_id and _entry_matches_auth(
                        entry, user_input
                    ):
                        return self.async_abort(reason="already_configured")
            else:
                for entry in self._async_current_entries(include_ignore=False):
                    if _entry_matches_auth(entry, user_input):
                        return self.async_abort(reason="already_configured")
                self._async_abort_entries_match(
                    {
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_BASE_URL: user_input[CONF_BASE_URL],
                    }
                )
            try:
                await validate_input(self.hass, user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except RateLimitError:
                errors["base"] = "rate_limited"
            except BadRequestError as err:
                if _error_mentions_model(err):
                    errors[CONF_MODEL] = "invalid_model"
                else:
                    errors["base"] = "unknown"
            except ModelError:
                errors[CONF_MODEL] = "invalid_model"
            except APIConnectionError:
                errors["base"] = "cannot_connect"
            except OpenResponsesStreamValidationError:
                errors["base"] = "unknown"
            except OpenResponsesError:
                errors["base"] = "unknown"
            else:
                default_conversation_options = {
                    **RECOMMENDED_CONVERSATION_OPTIONS,
                    CONF_GENERATED_DEFAULT_SUBENTRY: True,
                    CONF_MODEL: user_input[CONF_MODEL],
                }
                if self.source == SOURCE_REAUTH:
                    reauth_entry = self._get_reauth_entry()
                    _async_update_default_subentry_models(
                        self.hass, reauth_entry, user_input[CONF_MODEL]
                    )
                    return self.async_update_reload_and_abort(
                        reauth_entry, data_updates=user_input
                    )
                return self.async_create_entry(
                    title="Open Responses",
                    data=user_input,
                    subentries=[
                        {
                            "subentry_type": "conversation",
                            "data": default_conversation_options,
                            "title": DEFAULT_CONVERSATION_NAME,
                            "unique_id": None,
                        },
                    ],
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "docs_url": "https://www.home-assistant.io/integrations/open_responses",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, self._get_reauth_entry().data
                ),
            )

        return await self.async_step_user(user_input)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "conversation": OpenResponsesSubentryFlowHandler,
        }


class OpenResponsesSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing Open Responses subentries."""

    options: dict[str, Any]

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == SOURCE_USER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        self.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        return await self.async_step_init(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage subentry options."""
        entry = self._get_entry()
        if entry.state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        errors: dict[str, str] = {}
        if user_input is not None:
            form_options = self.options | user_input
            try:
                await validate_input(
                    self.hass,
                    {
                        CONF_API_KEY: entry.data[CONF_API_KEY],
                        CONF_BASE_URL: entry.data[CONF_BASE_URL],
                        CONF_MODEL: user_input[CONF_MODEL],
                    },
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except RateLimitError:
                errors["base"] = "rate_limited"
            except BadRequestError as err:
                if _error_mentions_model(err):
                    errors[CONF_MODEL] = "invalid_model"
                else:
                    errors["base"] = "unknown"
            except ModelError:
                errors[CONF_MODEL] = "invalid_model"
            except APIConnectionError:
                errors["base"] = "cannot_connect"
            except OpenResponsesStreamValidationError:
                errors["base"] = "unknown"
            except OpenResponsesError:
                errors["base"] = "unknown"
            else:
                subentry_data = user_input.copy()
                if not self._is_new and self._get_reconfigure_subentry().data.get(
                    CONF_GENERATED_DEFAULT_SUBENTRY
                ):
                    subentry_data[CONF_GENERATED_DEFAULT_SUBENTRY] = True
                if not subentry_data.get(CONF_LLM_HASS_API):
                    subentry_data.pop(CONF_LLM_HASS_API, None)
                if self._is_new:
                    return self.async_create_entry(
                        title=subentry_data.pop(CONF_NAME),
                        data=subentry_data,
                    )
                return self.async_update_and_abort(
                    entry,
                    self._get_reconfigure_subentry(),
                    data=subentry_data,
                )
        else:
            form_options = self.options

        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]
        if suggested_llm_apis := form_options.get(CONF_LLM_HASS_API):
            valid_apis = {api.id for api in llm.async_get_apis(self.hass)}
            form_options[CONF_LLM_HASS_API] = [
                api for api in suggested_llm_apis if api in valid_apis
            ]

        step_schema: VolDictType = {}
        if self._is_new:
            step_schema[vol.Required(CONF_NAME, default=DEFAULT_CONVERSATION_NAME)] = (
                str
            )

        step_schema.update(
            {
                vol.Required(
                    CONF_MODEL,
                    default=form_options.get(CONF_MODEL, entry.data[CONF_MODEL]),
                ): str,
                vol.Optional(
                    CONF_MAX_OUTPUT_TOKENS,
                    default=form_options.get(
                        CONF_MAX_OUTPUT_TOKENS, RECOMMENDED_MAX_OUTPUT_TOKENS
                    ),
                ): vol.All(
                    NumberSelector(NumberSelectorConfig(min=1, max=128000, step=100)),
                    vol.Coerce(int),
                ),
                vol.Optional(
                    CONF_STORE_RESPONSES,
                    default=form_options.get(
                        CONF_STORE_RESPONSES, RECOMMENDED_STORE_RESPONSES
                    ),
                ): bool,
            }
        )

        step_schema.update(
            {
                vol.Optional(
                    CONF_PROMPT,
                    description={
                        "suggested_value": form_options.get(
                            CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                        )
                    },
                ): TemplateSelector(),
                vol.Optional(
                    CONF_LLM_HASS_API,
                    default=form_options.get(
                        CONF_LLM_HASS_API,
                        RECOMMENDED_CONVERSATION_OPTIONS[CONF_LLM_HASS_API],
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(options=hass_apis, multiple=True)
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), form_options
            ),
            errors=errors,
        )
