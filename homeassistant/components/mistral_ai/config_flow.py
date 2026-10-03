"""Config flow for Mistral AI integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from httpx import HTTPError
from mistralai.client import errors as mistral_errors
import probatio

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)
from homeassistant.helpers.typing import VolDictType

from .api import async_create_client, get_model_ids
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    MISTRAL_MODELS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)

DATA_MODELS_CACHE = "mistral_ai_models_cache"

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
    }
)


async def _async_fetch_models(
    hass: HomeAssistant, api_key: str, fallback: list[str]
) -> list[str]:
    """Fetch available model IDs, with a fallback.

    The fallback is not cached: a transient failure should be retried on the
    next visit instead of being pinned until Home Assistant restarts.
    """
    cache = hass.data.setdefault(DATA_MODELS_CACHE, {})
    if api_key in cache:
        return cache[api_key]

    try:
        client = await async_create_client(hass, api_key)
        models = await get_model_ids(client, "completion_chat")
    except mistral_errors.MistralError, mistral_errors.NoResponseError, HTTPError:
        return list(fallback)

    if not models:
        return list(fallback)

    cache[api_key] = models
    return models


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    client = await async_create_client(hass, data[CONF_API_KEY])
    await client.models.list_async(timeout_ms=10_000)


class MistralAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mistral AI."""

    VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self._async_step_api_key(user_input)

    async def _async_step_api_key(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Handle an API key form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            try:
                await validate_input(self.hass, user_input)
            except mistral_errors.NoResponseError, HTTPError:
                errors["base"] = "cannot_connect"
            except mistral_errors.MistralError as err:
                if err.status_code in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    entry = self._get_reauth_entry()
                    if entry.update_listeners:
                        return self.async_update_and_abort(
                            entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                        )
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                    )
                return self.async_create_entry(
                    title="Mistral",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                    subentries=[
                        {
                            "subentry_type": "conversation",
                            "data": RECOMMENDED_CONVERSATION_OPTIONS,
                            "title": DEFAULT_CONVERSATION_NAME,
                            "unique_id": None,
                        },
                    ],
                )

        return self.async_show_form(
            step_id="user" if self.source != SOURCE_REAUTH else "reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauth confirmation step."""
        return await self._async_step_api_key(user_input)

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentries supported by this integration."""
        return {
            "conversation": MistralConversationSubentryFlowHandler,
        }


class MistralConversationSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing the conversation subentry."""

    options: dict[str, Any]

    @property
    def _is_new(self) -> bool:
        """Return whether this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step of a subentry flow."""
        self.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the reconfigure step of a subentry flow."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the init step of a subentry flow."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        options = self.options
        errors: dict[str, str] = {}

        step_schema: VolDictType = {}

        if self._is_new:
            step_schema[
                probatio.Required(CONF_NAME, default=DEFAULT_CONVERSATION_NAME)
            ] = str

        api_key = self._get_entry().data[CONF_API_KEY]

        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(label=api.name, value=api.id)
            for api in llm.async_get_apis(self.hass)
        ]
        if suggested_llm_apis := options.get(CONF_LLM_HASS_API):
            if isinstance(suggested_llm_apis, str):
                suggested_llm_apis = [suggested_llm_apis]
            valid_apis = {api.id for api in llm.async_get_apis(self.hass)}
            options[CONF_LLM_HASS_API] = [
                api for api in suggested_llm_apis if api in valid_apis
            ]

        model_options = await _async_fetch_models(self.hass, api_key, MISTRAL_MODELS)
        step_schema.update(
            {
                probatio.Optional(
                    CONF_RECOMMENDED,
                    default=options.get(CONF_RECOMMENDED, True),
                ): bool,
                probatio.Optional(
                    CONF_CHAT_MODEL,
                    default=options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=model_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                probatio.Optional(
                    CONF_PROMPT,
                    description={
                        "suggested_value": options.get(
                            CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                        )
                    },
                ): TemplateSelector(),
                probatio.Optional(CONF_LLM_HASS_API): SelectSelector(
                    SelectSelectorConfig(options=hass_apis, multiple=True)
                ),
            }
        )

        if user_input is not None:
            if user_input.get(CONF_LLM_HASS_API) is None:
                user_input.pop(CONF_LLM_HASS_API, None)
            if user_input.get(CONF_RECOMMENDED):
                if self._is_new:
                    return self.async_create_entry(
                        title=user_input.pop(CONF_NAME),
                        data=user_input,
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=user_input,
                )

            options.update(user_input)
            if CONF_LLM_HASS_API in options and CONF_LLM_HASS_API not in user_input:
                options.pop(CONF_LLM_HASS_API)
            return await self.async_step_advanced()

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(step_schema), options
            ),
            errors=errors,
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the advanced settings step."""
        options = self.options

        if user_input is not None:
            options.update(user_input)
            if self._is_new:
                return self.async_create_entry(
                    title=options.pop(CONF_NAME),
                    data=options,
                )
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=options,
            )

        return self.async_show_form(
            step_id="advanced",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_MAX_TOKENS,
                        default=options.get(CONF_MAX_TOKENS, DEFAULT[CONF_MAX_TOKENS]),
                    ): int,
                    probatio.Optional(
                        CONF_TEMPERATURE,
                        default=options.get(
                            CONF_TEMPERATURE, DEFAULT[CONF_TEMPERATURE]
                        ),
                    ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
                    probatio.Optional(
                        CONF_TOP_P,
                        default=options.get(CONF_TOP_P, DEFAULT[CONF_TOP_P]),
                    ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
                }
            ),
        )
