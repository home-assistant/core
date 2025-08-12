"""Config flow for Google Generative AI Conversation integration."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
import logging
from typing import Any, cast

from google import genai
from google.genai.errors import APIError, ClientError
from requests.exceptions import Timeout
import voluptuous as vol

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

from .const import (
    CONF_CHAT_MODEL,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    CONF_USE_GOOGLE_SEARCH_TOOL,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_STT_PROMPT,
    DEFAULT_TITLE,
    DEFAULT_TTS_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_STT_MODEL,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
    RECOMMENDED_TTS_MODEL,
    RECOMMENDED_TTS_OPTIONS,
    RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
    TIMEOUT_MILLIS,
)

_LOGGER = logging.getLogger(__name__)

STEP_API_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = await hass.async_add_executor_job(
        partial(genai.Client, api_key=data[CONF_API_KEY])
    )
    await client.aio.models.list(
        config={
            "http_options": {
                "timeout": TIMEOUT_MILLIS,
            },
            "query_base": True,
        }
    )


class GoogleGenerativeAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Generative AI Conversation."""

    VERSION = 2
    MINOR_VERSION = 4

    async def async_step_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                await validate_input(self.hass, user_input)
            except (APIError, Timeout) as err:
                if isinstance(err, ClientError) and "API_KEY_INVALID" in str(err):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data=user_input,
                    )
                return self.async_create_entry(
                    title=DEFAULT_TITLE,
                    data=user_input,
                    subentries=[
                        {
                            "subentry_type": "conversation",
                            "data": RECOMMENDED_CONVERSATION_OPTIONS,
                            "title": DEFAULT_CONVERSATION_NAME,
                            "unique_id": None,
                        },
                        {
                            "subentry_type": "tts",
                            "data": RECOMMENDED_TTS_OPTIONS,
                            "title": DEFAULT_TTS_NAME,
                            "unique_id": None,
                        },
                        {
                            "subentry_type": "ai_task_data",
                            "data": RECOMMENDED_AI_TASK_OPTIONS,
                            "title": DEFAULT_AI_TASK_NAME,
                            "unique_id": None,
                        },
                        {
                            "subentry_type": "stt",
                            "data": RECOMMENDED_STT_OPTIONS,
                            "title": DEFAULT_STT_NAME,
                            "unique_id": None,
                        },
                    ],
                )
        return self.async_show_form(
            step_id="api",
            data_schema=STEP_API_DATA_SCHEMA,
            description_placeholders={
                "api_key_url": "https://aistudio.google.com/app/apikey"
            },
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self.async_step_api()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is not None:
            return await self.async_step_api()

        reauth_entry = self._get_reauth_entry()
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                CONF_NAME: reauth_entry.title,
                CONF_API_KEY: reauth_entry.data.get(CONF_API_KEY, ""),
            },
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "conversation": LLMSubentryFlowHandler,
            "stt": LLMSubentryFlowHandler,
            "tts": LLMSubentryFlowHandler,
            "ai_task_data": LLMSubentryFlowHandler,
        }


class LLMSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing conversation subentries."""

    last_rendered_recommended = False

    @property
    def _genai_client(self) -> genai.Client:
        """Return the Google Generative AI client."""
        return self._get_entry().runtime_data

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_set_options(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Set conversation options."""
        # abort if entry is not loaded
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        errors: dict[str, str] = {}

        if user_input is None:
            if self._is_new:
                options: dict[str, Any]
                if self._subentry_type == "tts":
                    options = RECOMMENDED_TTS_OPTIONS.copy()
                elif self._subentry_type == "ai_task_data":
                    options = RECOMMENDED_AI_TASK_OPTIONS.copy()
                elif self._subentry_type == "stt":
                    options = RECOMMENDED_STT_OPTIONS.copy()
                else:
                    options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
            else:
                # If this is a reconfiguration, we need to copy the existing options
                # so that we can show the current values in the form.
                options = self._get_reconfigure_subentry().data.copy()

            self.last_rendered_recommended = cast(
                bool, options.get(CONF_RECOMMENDED, False)
            )

        else:
            if user_input[CONF_RECOMMENDED] == self.last_rendered_recommended:
                if not user_input.get(CONF_LLM_HASS_API):
                    user_input.pop(CONF_LLM_HASS_API, None)
                # Don't allow to save options that enable the Google Search tool with an Assist API
                if not (
                    user_input.get(CONF_LLM_HASS_API)
                    and user_input.get(CONF_USE_GOOGLE_SEARCH_TOOL, False) is True
                ):
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
                errors[CONF_USE_GOOGLE_SEARCH_TOOL] = "invalid_google_search_option"

            # Re-render the options again, now with the recommended options shown/hidden
            self.last_rendered_recommended = user_input[CONF_RECOMMENDED]

            options = user_input

        schema = await google_generative_ai_config_option_schema(
            self.hass, self._is_new, self._subentry_type, options, self._genai_client
        )
        return self.async_show_form(
            step_id="set_options", data_schema=vol.Schema(schema), errors=errors
        )

    async_step_reconfigure = async_step_set_options
    async_step_user = async_step_set_options


async def google_generative_ai_config_option_schema(
    hass: HomeAssistant,
    is_new: bool,
    subentry_type: str,
    options: Mapping[str, Any],
    genai_client: genai.Client,
) -> dict:
    """Return a schema for Google Generative AI completion options."""
    hass_apis: list[SelectOptionDict] = [
        SelectOptionDict(
            label=api.name,
            value=api.id,
        )
        for api in llm.async_get_apis(hass)
    ]
    if (suggested_llm_apis := options.get(CONF_LLM_HASS_API)) and isinstance(
        suggested_llm_apis, str
    ):
        suggested_llm_apis = [suggested_llm_apis]

    if is_new:
        if CONF_NAME in options:
            default_name = options[CONF_NAME]
        elif subentry_type == "tts":
            default_name = DEFAULT_TTS_NAME
        elif subentry_type == "ai_task_data":
            default_name = DEFAULT_AI_TASK_NAME
        elif subentry_type == "stt":
            default_name = DEFAULT_STT_NAME
        else:
            default_name = DEFAULT_CONVERSATION_NAME
        schema: dict[vol.Required | vol.Optional, Any] = {
            vol.Required(CONF_NAME, default=default_name): str,
        }
    else:
        schema = {}

    if subentry_type == "conversation":
        schema.update(
            {
                vol.Optional(
                    CONF_PROMPT,
                    description={
                        "suggested_value": options.get(
                            CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                        )
                    },
                ): TemplateSelector(),
                vol.Optional(
                    CONF_LLM_HASS_API,
                    description={"suggested_value": suggested_llm_apis},
                ): SelectSelector(
                    SelectSelectorConfig(options=hass_apis, multiple=True)
                ),
            }
        )
    elif subentry_type == "stt":
        schema.update(
            {
                vol.Optional(
                    CONF_PROMPT,
                    description={
                        "suggested_value": options.get(CONF_PROMPT, DEFAULT_STT_PROMPT)
                    },
                ): TemplateSelector(),
            }
        )

    schema.update(
        {
            vol.Required(
                CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False)
            ): bool,
        }
    )

    if options.get(CONF_RECOMMENDED):
        return schema

    api_models_pager = await genai_client.aio.models.list(config={"query_base": True})
    api_models = [api_model async for api_model in api_models_pager]
    models = [
        SelectOptionDict(
            label=api_model.name.lstrip("models/"),
            value=api_model.name,
        )
        for api_model in sorted(
            api_models, key=lambda x: (x.name or "").lstrip("models/")
        )
        if (
            api_model.name
            and ("tts" in api_model.name) == (subentry_type == "tts")
            and "vision" not in api_model.name
            and api_model.supported_actions
            and "generateContent" in api_model.supported_actions
        )
    ]

    harm_block_thresholds: list[SelectOptionDict] = [
        SelectOptionDict(
            label="Block none",
            value="BLOCK_NONE",
        ),
        SelectOptionDict(
            label="Block few",
            value="BLOCK_ONLY_HIGH",
        ),
        SelectOptionDict(
            label="Block some",
            value="BLOCK_MEDIUM_AND_ABOVE",
        ),
        SelectOptionDict(
            label="Block most",
            value="BLOCK_LOW_AND_ABOVE",
        ),
    ]
    harm_block_thresholds_selector = SelectSelector(
        SelectSelectorConfig(
            mode=SelectSelectorMode.DROPDOWN, options=harm_block_thresholds
        )
    )

    if subentry_type == "tts":
        default_model = RECOMMENDED_TTS_MODEL
    elif subentry_type == "stt":
        default_model = RECOMMENDED_STT_MODEL
    else:
        default_model = RECOMMENDED_CHAT_MODEL

    schema.update(
        {
            vol.Optional(
                CONF_CHAT_MODEL,
                description={"suggested_value": options.get(CONF_CHAT_MODEL)},
                default=default_model,
            ): SelectSelector(
                SelectSelectorConfig(mode=SelectSelectorMode.DROPDOWN, options=models)
            ),
            vol.Optional(
                CONF_TEMPERATURE,
                description={"suggested_value": options.get(CONF_TEMPERATURE)},
                default=RECOMMENDED_TEMPERATURE,
            ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
            vol.Optional(
                CONF_TOP_P,
                description={"suggested_value": options.get(CONF_TOP_P)},
                default=RECOMMENDED_TOP_P,
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Optional(
                CONF_TOP_K,
                description={"suggested_value": options.get(CONF_TOP_K)},
                default=RECOMMENDED_TOP_K,
            ): int,
            vol.Optional(
                CONF_MAX_TOKENS,
                description={"suggested_value": options.get(CONF_MAX_TOKENS)},
                default=RECOMMENDED_MAX_TOKENS,
            ): int,
            vol.Optional(
                CONF_HARASSMENT_BLOCK_THRESHOLD,
                description={
                    "suggested_value": options.get(CONF_HARASSMENT_BLOCK_THRESHOLD)
                },
                default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
            ): harm_block_thresholds_selector,
            vol.Optional(
                CONF_HATE_BLOCK_THRESHOLD,
                description={"suggested_value": options.get(CONF_HATE_BLOCK_THRESHOLD)},
                default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
            ): harm_block_thresholds_selector,
            vol.Optional(
                CONF_SEXUAL_BLOCK_THRESHOLD,
                description={
                    "suggested_value": options.get(CONF_SEXUAL_BLOCK_THRESHOLD)
                },
                default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
            ): harm_block_thresholds_selector,
            vol.Optional(
                CONF_DANGEROUS_BLOCK_THRESHOLD,
                description={
                    "suggested_value": options.get(CONF_DANGEROUS_BLOCK_THRESHOLD)
                },
                default=RECOMMENDED_HARM_BLOCK_THRESHOLD,
            ): harm_block_thresholds_selector,
        }
    )
    if subentry_type == "conversation":
        schema.update(
            {
                vol.Optional(
                    CONF_USE_GOOGLE_SEARCH_TOOL,
                    description={
                        "suggested_value": options.get(CONF_USE_GOOGLE_SEARCH_TOOL),
                    },
                    default=RECOMMENDED_USE_GOOGLE_SEARCH_TOOL,
                ): bool,
            }
        )

    return schema
