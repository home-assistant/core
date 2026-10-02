"""Config flow for Mistral AI integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from mistralai.client import Mistral
import mistralai.client.utils.security  # noqa: F401
import probatio

from homeassistant.config_entries import (
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

from .api import get_model_ids
from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_TTS_NAME,
    DOMAIN,
    MISTRAL_MODELS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_STT_MODEL,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TTS_MODEL,
    RECOMMENDED_TTS_OPTIONS,
    STT_MODELS,
    TTS_MODELS,
)

_LOGGER = logging.getLogger(__name__)

DATA_MODELS_CACHE = "mistral_ai_models_cache"

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_API_KEY): str,
    }
)


def _validate_api_key(api_key: str) -> None:
    """Validate the API key by listing models."""
    client = Mistral(api_key=api_key)
    _ = client.models

    client.models.list(timeout_ms=10_000)


async def _async_fetch_models(
    hass: HomeAssistant, api_key: str, capability: str, fallback: list[str]
) -> list[str]:
    """Fetch available model IDs for a capability, with a fallback."""
    cache = hass.data.setdefault(DATA_MODELS_CACHE, {})
    cache_key = f"{api_key}:{capability}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        models = await hass.async_add_executor_job(get_model_ids, api_key, capability)
    except Exception:  # noqa: BLE001
        models = []
    if not models:
        models = list(fallback)
    cache[cache_key] = models
    return models


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    await hass.async_add_executor_job(_validate_api_key, data[CONF_API_KEY])


class MistralAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mistral AI."""

    VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_API_KEY: user_input[CONF_API_KEY]})
            try:
                await validate_input(self.hass, user_input)
            except Exception as err:  # noqa: BLE001
                status_code = getattr(err, "status_code", None)
                if status_code in (401, 403):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            else:
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
                        {
                            "subentry_type": "stt",
                            "data": RECOMMENDED_STT_OPTIONS,
                            "title": DEFAULT_STT_NAME,
                            "unique_id": None,
                        },
                        {
                            "subentry_type": "tts",
                            "data": RECOMMENDED_TTS_OPTIONS,
                            "title": DEFAULT_TTS_NAME,
                            "unique_id": None,
                        },
                    ],
                )

        return self.async_show_form(
            step_id="user",
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
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA
            )

        return await self.async_step_user(user_input)

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentries supported by this integration."""
        return {
            "conversation": MistralConversationSubentryFlowHandler,
            "stt": MistralAudioSubentryFlowHandler,
            "tts": MistralAudioSubentryFlowHandler,
        }


class _MistralSubentryFlowHandler(ConfigSubentryFlow):
    """Base flow for managing Mistral AI subentries."""

    options: dict[str, Any]

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the advanced settings step."""
        raise NotImplementedError

    @property
    def _is_new(self) -> bool:
        """Return whether this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the user step of a subentry flow."""
        if self._subentry_type == "conversation":
            self.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        elif self._subentry_type == "stt":
            self.options = RECOMMENDED_STT_OPTIONS.copy()
        else:
            self.options = RECOMMENDED_TTS_OPTIONS.copy()
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
            if self._subentry_type == "conversation":
                default_name = DEFAULT_CONVERSATION_NAME
            elif self._subentry_type == "stt":
                default_name = DEFAULT_STT_NAME
            else:
                default_name = DEFAULT_TTS_NAME
            step_schema[probatio.Required(CONF_NAME, default=default_name)] = str

        api_key = self._get_entry().data[CONF_API_KEY]

        if self._subentry_type == "conversation":
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

            model_options = await _async_fetch_models(
                self.hass, api_key, "completion_chat", MISTRAL_MODELS
            )
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
        elif self._subentry_type == "stt":
            model_options = await _async_fetch_models(
                self.hass, api_key, "audio_transcription", STT_MODELS
            )
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_CHAT_MODEL,
                        default=options.get(CONF_CHAT_MODEL, RECOMMENDED_STT_MODEL),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=model_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                }
            )
        else:
            model_options = await _async_fetch_models(
                self.hass, api_key, "audio_speech", TTS_MODELS
            )
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_CHAT_MODEL,
                        default=options.get(CONF_CHAT_MODEL, RECOMMENDED_TTS_MODEL),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=model_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                }
            )

        if user_input is not None:
            if self._subentry_type == "conversation":
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
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(step_schema), options
            ),
            errors=errors,
        )


class MistralConversationSubentryFlowHandler(_MistralSubentryFlowHandler):
    """Flow for managing the conversation subentry."""

    @override
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


class MistralAudioSubentryFlowHandler(_MistralSubentryFlowHandler):
    """Flow for managing the STT and TTS subentries."""
