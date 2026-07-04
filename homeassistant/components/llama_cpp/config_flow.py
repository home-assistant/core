"""Config flow for llama.cpp integration."""

import logging
from typing import Any, cast, override

import openai
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_PROMPT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
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

from .api import (
    async_create_client,
    async_list_models,
    async_validate_completions,
    model_name_to_title,
    recommended_model,
)
from .const import (
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_RECOMMENDED,
    CONF_STREAMING,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_BASE_URL,
    DOMAIN,
    LOGGER,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
        vol.Optional(CONF_API_KEY): str,
    }
)


class LlamaCppConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for llama.cpp."""

    VERSION = 1

    data: dict[str, Any] | None = None
    client: openai.AsyncOpenAI | None = None
    models: list[str] | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                self.client = await async_create_client(self.hass, user_input)
                self.models = await async_list_models(self.client)
            except HomeAssistantError as err:
                LOGGER.error("Connection validation failed: %s", err)
                errors["base"] = err.translation_key or "unknown"
            except Exception:  # pylint: disable=broad-except # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.data = user_input
                return await self.async_step_model()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle selecting a model."""
        assert self.client is not None
        assert self.models is not None
        assert self.data is not None
        errors = {}
        if user_input is not None:
            model = user_input[CONF_CHAT_MODEL]
            try:
                await async_validate_completions(
                    self.client,
                    model=model,
                    stream=False,
                )
            except HomeAssistantError as err:
                LOGGER.error("Model completion validation failed: %s", err)
                errors["base"] = err.translation_key or "unknown"
            else:
                stream_support = True
                try:
                    await async_validate_completions(
                        self.client,
                        model=model,
                        stream=True,
                    )
                except HomeAssistantError:
                    stream_support = False

                base_options = {
                    **user_input,
                }
                return self.async_create_entry(
                    title=self.data[CONF_BASE_URL],
                    data={
                        **self.data,
                        CONF_STREAMING: stream_support,
                    },
                    subentries=[
                        {
                            "subentry_type": "conversation",
                            "data": {
                                CONF_RECOMMENDED: True,
                                CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
                                **base_options,
                            },
                            "title": model_name_to_title(model),
                            "unique_id": None,
                        },
                    ],
                )

        return self.async_show_form(
            step_id="model",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_CHAT_MODEL,
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=self.models,
                                translation_key=CONF_CHAT_MODEL,
                                mode=SelectSelectorMode.DROPDOWN,
                                custom_value=True,
                            ),
                        ),
                    }
                ),
                {
                    CONF_CHAT_MODEL: (user_input or {}).get(
                        CONF_CHAT_MODEL, recommended_model(self.models)
                    ),
                },
            ),
            errors=errors,
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "conversation": ConversationSubentryFlowHandler,
        }


class ConversationSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing conversation subentries."""

    last_rendered_recommended = False
    options: dict[str, Any] | None = None
    models: list[str] | None = None

    @property
    def _openai_client(self) -> openai.AsyncOpenAI:
        """Return the OpenAI client."""
        return cast(openai.AsyncOpenAI, self._get_entry().runtime_data)

    async def _get_models(self) -> list[str] | None:
        """Return the list of models."""
        if self.models is None:
            self.models = await async_list_models(self._openai_client)
        return self.models

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        try:
            models = await self._get_models()
        except HomeAssistantError:
            return self.async_abort(reason="cannot_connect")
        self.options = {
            CONF_RECOMMENDED: True,
            CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
            CONF_CHAT_MODEL: recommended_model(models),
        }
        self.last_rendered_recommended = cast(
            bool, self.options.get(CONF_RECOMMENDED, False)
        )
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        # abort if entry is not loaded
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if self.options is None:
            self.options = self._get_reconfigure_subentry().data.copy()
            self.last_rendered_recommended = cast(
                bool, self.options.get(CONF_RECOMMENDED, False)
            )

        try:
            models = await self._get_models()
        except HomeAssistantError:
            return self.async_abort(reason="cannot_connect")

        options = self.options

        if user_input is not None:
            model = user_input[CONF_CHAT_MODEL]
            try:
                await async_validate_completions(
                    self._openai_client,
                    model=model,
                    stream=self._get_entry().data.get(CONF_STREAMING, False),
                )
            except HomeAssistantError as err:
                LOGGER.error("Model completion validation failed: %s", err)
                return self.async_show_form(
                    step_id="init",
                    data_schema=self.add_suggested_values_to_schema(
                        vol.Schema(
                            llama_cpp_config_option_schema(self.hass, options, models)
                        ),
                        user_input,
                    ),
                    errors={"base": err.translation_key or "unknown"},
                )

            if user_input[CONF_RECOMMENDED] == self.last_rendered_recommended:
                if self.source == "user":
                    return self.async_create_entry(
                        title=model_name_to_title(user_input[CONF_CHAT_MODEL]),
                        data=user_input,
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=user_input,
                    title=model_name_to_title(user_input[CONF_CHAT_MODEL]),
                )

            self.last_rendered_recommended = user_input[CONF_RECOMMENDED]

            options = {
                CONF_RECOMMENDED: user_input[CONF_RECOMMENDED],
                CONF_PROMPT: user_input[CONF_PROMPT],
                CONF_CHAT_MODEL: user_input[CONF_CHAT_MODEL],
                CONF_LLM_HASS_API: user_input.get(CONF_LLM_HASS_API, []),
            }

        schema = llama_cpp_config_option_schema(self.hass, options, models)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(schema), options
            ),
        )


def llama_cpp_config_option_schema(
    hass: HomeAssistant,
    options: dict[str, Any],
    models: list[str] | None = None,
) -> dict:
    """Return a schema for llama.cpp completion options."""
    hass_apis: list[SelectOptionDict] = [
        SelectOptionDict(
            label=api.name,
            value=api.id,
        )
        for api in llm.async_get_apis(hass)
    ]
    LOGGER.debug("Available LLM APIs: %s", hass_apis)

    schema: dict[vol.Required | vol.Optional, Any] = {}

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
            ): SelectSelector(SelectSelectorConfig(options=hass_apis, multiple=True)),
        }
    )
    schema.update(
        {
            vol.Optional(
                CONF_CHAT_MODEL,
                description={"suggested_value": options.get(CONF_CHAT_MODEL)},
                default=options.get(CONF_CHAT_MODEL, recommended_model(models)),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=models or [],
                    translation_key=CONF_CHAT_MODEL,
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                ),
            ),
            vol.Required(
                CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False)
            ): bool,
        }
    )

    if options.get(CONF_RECOMMENDED):
        return schema

    schema.update(
        {
            vol.Optional(
                CONF_MAX_TOKENS,
                description={"suggested_value": options.get(CONF_MAX_TOKENS)},
                default=RECOMMENDED_MAX_TOKENS,
            ): int,
            vol.Optional(
                CONF_TOP_P,
                description={"suggested_value": options.get(CONF_TOP_P)},
                default=RECOMMENDED_TOP_P,
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Optional(
                CONF_TEMPERATURE,
                description={"suggested_value": options.get(CONF_TEMPERATURE)},
                default=RECOMMENDED_TEMPERATURE,
            ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
        }
    )
    return schema
