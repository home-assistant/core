"""Config flow for OpenRouter integration."""

import logging
from typing import Any, override

import probatio
from python_open_router import (
    Model,
    OpenRouterClient,
    OpenRouterError,
    SupportedParameter,
)

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)

from .const import (
    CONF_OUTPUT_MODALITIES,
    CONF_PROMPT,
    CONF_TTS_SPEED,
    CONF_TTS_VOICE,
    CONF_WEB_SEARCH,
    DOMAIN,
    FALLBACK_TTS_VOICES,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_TTS_SPEED,
    RECOMMENDED_TTS_VOICE,
)

_LOGGER = logging.getLogger(__name__)


class OpenRouterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenRouter."""

    VERSION = 1
    MINOR_VERSION = 4

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {
            "conversation": ConversationFlowHandler,
            "ai_task_data": AITaskDataFlowHandler,
            "tts": TtsFlowHandler,
        }

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            client = OpenRouterClient(
                user_input[CONF_API_KEY], async_get_clientsession(self.hass)
            )
            try:
                key_data = await client.get_key_data()
            except OpenRouterError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=key_data.label,
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                }
            ),
            errors=errors,
        )


class OpenRouterSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for OpenRouter."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.models: dict[str, Model] = {}

    async def _get_models(self, output_modalities: str | None = None) -> None:
        """Fetch models from OpenRouter, optionally filtered by output modality."""
        entry = self._get_entry()
        client = OpenRouterClient(
            entry.data[CONF_API_KEY], async_get_clientsession(self.hass)
        )
        models = await client.get_models(output_modalities=output_modalities)
        self.models = {model.id: model for model in models}


class ConversationFlowHandler(OpenRouterSubentryFlowHandler):
    """Handle conversation subentry flow."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self.options: dict[str, Any] = {}

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == SOURCE_USER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create a conversation agent."""
        self.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        return await self.async_step_init(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a conversation agent."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage conversation agent configuration."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            if user_input.get(CONF_LLM_HASS_API) is None:
                user_input.pop(CONF_LLM_HASS_API, None)
            if self._is_new:
                return self.async_create_entry(
                    title=self.models[user_input[CONF_MODEL]].name, data=user_input
                )
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=user_input,
            )

        try:
            await self._get_models()
        except OpenRouterError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        options = [
            SelectOptionDict(value=model.id, label=model.name)
            for model in self.models.values()
        ]

        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]

        if suggested_llm_apis := self.options.get(CONF_LLM_HASS_API):
            valid_api_ids = {api["value"] for api in hass_apis}
            self.options[CONF_LLM_HASS_API] = [
                api for api in suggested_llm_apis if api in valid_api_ids
            ]

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_MODEL, default=self.options.get(CONF_MODEL)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN, sort=True
                        ),
                    ),
                    probatio.Optional(
                        CONF_PROMPT,
                        description={
                            "suggested_value": self.options.get(
                                CONF_PROMPT,
                                RECOMMENDED_CONVERSATION_OPTIONS[CONF_PROMPT],
                            )
                        },
                    ): TemplateSelector(),
                    probatio.Optional(
                        CONF_LLM_HASS_API,
                        default=self.options.get(
                            CONF_LLM_HASS_API,
                            RECOMMENDED_CONVERSATION_OPTIONS[CONF_LLM_HASS_API],
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(options=hass_apis, multiple=True)
                    ),
                    probatio.Optional(
                        CONF_WEB_SEARCH,
                        default=self.options.get(
                            CONF_WEB_SEARCH,
                            RECOMMENDED_CONVERSATION_OPTIONS[CONF_WEB_SEARCH],
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                "off",
                                "plugin",
                                "tool",
                                "tool_native",
                                "tool_exa",
                                "tool_firecrawl",
                                "tool_parallel",
                                "tool_perplexity",
                            ],
                            translation_key="web_search_modes",
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )


class AITaskDataFlowHandler(OpenRouterSubentryFlowHandler):
    """Handle AI task subentry flow."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self.options: dict[str, Any] = {}

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == SOURCE_USER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create an AI task."""
        self.options = {}
        return await self.async_step_init(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of an AI task."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage AI task configuration."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            model = self.models[user_input[CONF_MODEL]]
            user_input[CONF_OUTPUT_MODALITIES] = [
                str(modality) for modality in model.architecture.output_modalities
            ]
            if self._is_new:
                return self.async_create_entry(title=model.name, data=user_input)
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=user_input,
            )

        try:
            await self._get_models()
        except OpenRouterError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        options = [
            SelectOptionDict(value=model.id, label=model.name)
            for model in self.models.values()
            if SupportedParameter.STRUCTURED_OUTPUTS in model.supported_parameters
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_MODEL, default=self.options.get(CONF_MODEL)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN, sort=True
                        ),
                    ),
                }
            ),
        )


class TtsFlowHandler(OpenRouterSubentryFlowHandler):
    """Handle TTS subentry flow."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self.options: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create a TTS service."""
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage TTS model selection."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            self.options[CONF_MODEL] = user_input[CONF_MODEL]
            selected_model = self.models.get(user_input[CONF_MODEL])
            self.options["supported_voices"] = (
                selected_model.supported_voices if selected_model is not None else None
            )
            return await self.async_step_voice()

        try:
            await self._get_models(output_modalities="speech")
        except OpenRouterError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        if not self.models:
            return self.async_abort(reason="no_models")

        models = [
            SelectOptionDict(value=model.id, label=model.name)
            for model in self.models.values()
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_MODEL, default=models[0]["value"]): (
                        SelectSelector(
                            SelectSelectorConfig(
                                options=models,
                                mode=SelectSelectorMode.DROPDOWN,
                                sort=True,
                            ),
                        )
                    ),
                }
            ),
        )

    async def async_step_voice(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage TTS voice and speed selection."""
        if user_input is not None:
            self.options.update(user_input)
            model = self.models.get(self.options[CONF_MODEL])
            title = model.name if model else self.options[CONF_MODEL]
            return self.async_create_entry(title=title, data=self.options)

        model_voices = self.options.get("supported_voices")
        if model_voices:
            voices = [SelectOptionDict(value=v, label=v) for v in model_voices]
            default_voice = model_voices[0]
        else:
            voices = [
                SelectOptionDict(value=v, label=v.title()) for v in FALLBACK_TTS_VOICES
            ]
            default_voice = RECOMMENDED_TTS_VOICE

        return self.async_show_form(
            step_id="voice",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_TTS_VOICE, default=default_voice): (
                        SelectSelector(
                            SelectSelectorConfig(
                                options=voices,
                                mode=SelectSelectorMode.DROPDOWN,
                            ),
                        )
                    ),
                    probatio.Optional(
                        CONF_TTS_SPEED,
                        default=RECOMMENDED_TTS_SPEED,
                    ): probatio.All(
                        probatio.Coerce(float), probatio.Range(min=0.25, max=4.0)
                    ),
                }
            ),
        )
