"""Config flow for Azure OpenAI integration."""

from collections.abc import Mapping
import json
import logging
from typing import Any, override

import openai
import probatio

from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LLM_HASS_API,
    CONF_NAME,
    CONF_PROMPT,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.typing import VolDictType

from .capabilities import (
    IMAGE_MODEL_FAMILIES,
    RECOMMENDED_IMAGE_MODEL,
    RECOMMENDED_MODEL_FAMILIES,
    STT_MODEL_FAMILIES,
    TTS_MODEL_FAMILIES,
    get_capabilities,
)
from .client import create_client, normalize_base_url
from .const import (
    CONF_BASE_URL,
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_IMAGE_DEPLOYMENT,
    CONF_IMAGE_MODEL,
    CONF_MAX_TOKENS,
    CONF_MODEL_FAMILY,
    CONF_PRO_MODE,
    CONF_REASONING_EFFORT,
    CONF_REASONING_SUMMARY,
    CONF_RECOMMENDED,
    CONF_STT_MODEL,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_TTS_MODEL,
    CONF_TTS_SPEED,
    CONF_VERBOSITY,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_INLINE_CITATIONS,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_STT_PROMPT,
    DEFAULT_TTS_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CODE_INTERPRETER,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_PRO_MODE,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_REASONING_SUMMARY,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_TTS_OPTIONS,
    RECOMMENDED_TTS_SPEED,
    RECOMMENDED_VERBOSITY,
    RECOMMENDED_WEB_SEARCH,
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
    RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS,
    RECOMMENDED_WEB_SEARCH_USER_LOCATION,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_API_KEY): str,
        probatio.Required(CONF_BASE_URL): probatio.All(
            cv.string, probatio.Length(min=1)
        ),
    }
)
MODEL_FAMILY_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=RECOMMENDED_MODEL_FAMILIES,
        mode=SelectSelectorMode.DROPDOWN,
        custom_value=True,
    )
)
STT_MODEL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(STT_MODEL_FAMILIES),
        mode=SelectSelectorMode.DROPDOWN,
        custom_value=True,
    )
)
TTS_MODEL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(TTS_MODEL_FAMILIES),
        mode=SelectSelectorMode.DROPDOWN,
        custom_value=True,
    )
)
SECTION_RESPONSE = "response"
SECTION_REASONING = "reasoning"
SECTION_TOOLS = "tools"
SECTION_WEB_SEARCH = "web_search"
SECTION_IMAGE_GENERATION = "image_generation"


def _validate_connection_input(
    user_input: dict[str, Any], errors: dict[str, str]
) -> None:
    """Validate connection fields requiring non-whitespace content."""
    if not user_input[CONF_BASE_URL].strip():
        errors[CONF_BASE_URL] = "base_url_required"


def _normalize_image_config(
    section_input: dict[str, Any],
    options: dict[str, Any],
    errors: dict[str, str],
) -> None:
    """Normalize optional image deployment settings."""
    if CONF_IMAGE_DEPLOYMENT not in section_input:
        return

    section_input[CONF_IMAGE_DEPLOYMENT] = section_input[CONF_IMAGE_DEPLOYMENT].strip()
    if not section_input[CONF_IMAGE_DEPLOYMENT]:
        section_input.pop(CONF_IMAGE_DEPLOYMENT)
        section_input.pop(CONF_IMAGE_MODEL, None)
        options.pop(CONF_IMAGE_DEPLOYMENT, None)
        options.pop(CONF_IMAGE_MODEL, None)
        return

    section_input[CONF_IMAGE_MODEL] = section_input.get(CONF_IMAGE_MODEL, "").strip()
    if not section_input[CONF_IMAGE_MODEL]:
        errors[CONF_IMAGE_MODEL] = "model_required"


STEP_USER_SETUP_SCHEMA = STEP_USER_DATA_SCHEMA.extend(
    {
        probatio.Required("conversation"): section(
            probatio.Schema(
                {
                    probatio.Optional(CONF_CHAT_MODEL): str,
                    probatio.Optional(CONF_MODEL_FAMILY): MODEL_FAMILY_SELECTOR,
                }
            ),
            SectionConfig(collapsed=True),
        ),
        probatio.Required("ai_task_data"): section(
            probatio.Schema(
                {
                    probatio.Optional(CONF_CHAT_MODEL): str,
                    probatio.Optional(CONF_MODEL_FAMILY): MODEL_FAMILY_SELECTOR,
                }
            ),
            SectionConfig(collapsed=True),
        ),
        probatio.Required("stt"): section(
            probatio.Schema(
                {
                    probatio.Optional(CONF_CHAT_MODEL): str,
                    probatio.Optional(CONF_STT_MODEL): STT_MODEL_SELECTOR,
                    probatio.Optional(CONF_API_VERSION): str,
                }
            ),
            SectionConfig(collapsed=True),
        ),
        probatio.Required("tts"): section(
            probatio.Schema(
                {
                    probatio.Optional(CONF_CHAT_MODEL): str,
                    probatio.Optional(CONF_TTS_MODEL): TTS_MODEL_SELECTOR,
                }
            ),
            SectionConfig(collapsed=True),
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = create_client(hass, data)
    await client.models.list(timeout=10.0)


class OpenAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure OpenAI Conversation."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        is_onboarding = self.source not in (SOURCE_REAUTH, SOURCE_RECONFIGURE)

        conversation_deployment = ""
        conversation_family = ""
        ai_task_deployment = ""
        ai_task_family = ""
        stt_deployment = ""
        stt_model = ""
        stt_api_version = ""
        tts_deployment = ""
        tts_model = ""

        if user_input is not None:
            user_input = dict(user_input)
            _validate_connection_input(user_input, errors)

            if is_onboarding:
                conversation = user_input.get("conversation", {})
                ai_task = user_input.get("ai_task_data", {})
                stt_section = user_input.get("stt", {})
                tts_section = user_input.get("tts", {})

                conversation_deployment = conversation.get(CONF_CHAT_MODEL, "").strip()
                conversation_family = conversation.get(CONF_MODEL_FAMILY, "").strip()
                if bool(conversation_deployment) != bool(conversation_family):
                    errors["base"] = "deployment_model_family_required"
                elif conversation_family and (
                    "unsupported" in get_capabilities(conversation_family).features
                ):
                    errors["base"] = "model_not_supported"

                ai_task_deployment = ai_task.get(CONF_CHAT_MODEL, "").strip()
                ai_task_family = ai_task.get(CONF_MODEL_FAMILY, "").strip()
                if not errors:
                    if bool(ai_task_deployment) != bool(ai_task_family):
                        errors["base"] = "deployment_model_family_required"
                    elif ai_task_family and (
                        "unsupported" in get_capabilities(ai_task_family).features
                    ):
                        errors["base"] = "model_not_supported"

                stt_deployment = stt_section.get(CONF_CHAT_MODEL, "").strip()
                stt_model = stt_section.get(CONF_STT_MODEL, "").strip()
                stt_api_version = stt_section.get(CONF_API_VERSION, "").strip()
                if not errors and bool(stt_deployment) != bool(stt_model):
                    errors["base"] = "stt_deployment_model_required"

                tts_deployment = tts_section.get(CONF_CHAT_MODEL, "").strip()
                tts_model = tts_section.get(CONF_TTS_MODEL, "").strip()
                if not errors and bool(tts_deployment) != bool(tts_model):
                    errors["base"] = "tts_deployment_model_required"

        if user_input is not None and not errors:
            connection_data = {
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_BASE_URL: normalize_base_url(user_input[CONF_BASE_URL]),
            }
            self._async_abort_entries_match(
                {CONF_BASE_URL: connection_data[CONF_BASE_URL]}
            )
            if any(
                entry.entry_id != self.context.get("entry_id")
                and normalize_base_url(entry.data[CONF_BASE_URL])
                == connection_data[CONF_BASE_URL]
                for entry in self._async_current_entries(include_ignore=False)
            ):
                return self.async_abort(reason="already_configured")
            try:
                await validate_input(self.hass, connection_data)
            except openai.APIConnectionError:
                errors["base"] = "cannot_connect"
            except openai.AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
                    entry = (
                        self._get_reauth_entry()
                        if self.source == SOURCE_REAUTH
                        else self._get_reconfigure_entry()
                    )
                    if entry.update_listeners:
                        return self.async_update_and_abort(
                            entry, data_updates=connection_data
                        )
                    return self.async_update_reload_and_abort(
                        entry, data_updates=connection_data
                    )
                subentries: list[ConfigSubentryData] = []
                if conversation_deployment:
                    subentries.append(
                        {
                            "subentry_type": "conversation",
                            "data": {
                                **RECOMMENDED_CONVERSATION_OPTIONS,
                                CONF_CHAT_MODEL: conversation_deployment,
                                CONF_MODEL_FAMILY: conversation_family,
                            },
                            "title": DEFAULT_CONVERSATION_NAME,
                            "unique_id": None,
                        }
                    )
                if ai_task_deployment:
                    subentries.append(
                        {
                            "subentry_type": "ai_task_data",
                            "data": {
                                **RECOMMENDED_AI_TASK_OPTIONS,
                                CONF_CHAT_MODEL: ai_task_deployment,
                                CONF_MODEL_FAMILY: ai_task_family,
                            },
                            "title": DEFAULT_AI_TASK_NAME,
                            "unique_id": None,
                        }
                    )
                if stt_deployment:
                    stt_data: dict[str, Any] = {
                        **RECOMMENDED_STT_OPTIONS,
                        CONF_CHAT_MODEL: stt_deployment,
                        CONF_STT_MODEL: stt_model,
                    }
                    if stt_api_version:
                        stt_data[CONF_API_VERSION] = stt_api_version
                    subentries.append(
                        {
                            "subentry_type": "stt",
                            "data": stt_data,
                            "title": DEFAULT_STT_NAME,
                            "unique_id": None,
                        }
                    )
                if tts_deployment:
                    subentries.append(
                        {
                            "subentry_type": "tts",
                            "data": {
                                **RECOMMENDED_TTS_OPTIONS,
                                CONF_CHAT_MODEL: tts_deployment,
                                CONF_TTS_MODEL: tts_model,
                            },
                            "title": DEFAULT_TTS_NAME,
                            "unique_id": None,
                        }
                    )
                return self.async_create_entry(
                    title="Azure OpenAI",
                    data=connection_data,
                    subentries=subentries,
                )

        step_id = "user"
        if self.source == SOURCE_REAUTH:
            step_id = "reauth_confirm"
        elif self.source == SOURCE_RECONFIGURE:
            step_id = "reconfigure"
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SETUP_SCHEMA if step_id == "user" else STEP_USER_DATA_SCHEMA,
                user_input
                if user_input is not None
                else (
                    self._get_reconfigure_entry().data
                    if step_id == "reconfigure"
                    else None
                ),
            ),
            errors=errors,
            description_placeholders={
                "instructions_url": "https://ai.azure.com/",
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the connection settings."""
        return await self.async_step_user(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, self._get_reauth_entry().data
                ),
            )

        return await self.async_step_user(user_input)

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "conversation": OpenAISubentryFlowHandler,
            "ai_task_data": OpenAISubentryFlowHandler,
            "stt": OpenAISubentrySTTFlowHandler,
            "tts": OpenAISubentryTTSFlowHandler,
        }


class OpenAISubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing OpenAI subentries."""

    options: dict[str, Any]

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        if self._subentry_type == "ai_task_data":
            self.options = RECOMMENDED_AI_TASK_OPTIONS.copy()
        else:
            self.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        options = self.options
        errors: dict[str, str] = {}

        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]
        if suggested_llm_apis := options.get(CONF_LLM_HASS_API):
            if isinstance(suggested_llm_apis, str):
                suggested_llm_apis = [suggested_llm_apis]
            valid_apis = {api.id for api in llm.async_get_apis(self.hass)}
            options[CONF_LLM_HASS_API] = [
                api for api in suggested_llm_apis if api in valid_apis
            ]

        step_schema: VolDictType = {}

        if self._is_new:
            if self._subentry_type == "ai_task_data":
                default_name = DEFAULT_AI_TASK_NAME
            else:
                default_name = DEFAULT_CONVERSATION_NAME
            step_schema[probatio.Required(CONF_NAME, default=default_name)] = str

        if self._subentry_type == "conversation":
            step_schema.update(
                {
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

        step_schema[
            probatio.Required(
                CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False)
            )
        ] = bool
        step_schema[probatio.Required(CONF_CHAT_MODEL)] = probatio.All(
            cv.string, probatio.Length(min=1)
        )
        step_schema[probatio.Required(CONF_MODEL_FAMILY)] = MODEL_FAMILY_SELECTOR

        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_CHAT_MODEL] = user_input[CONF_CHAT_MODEL].strip()
            user_input[CONF_MODEL_FAMILY] = user_input[CONF_MODEL_FAMILY].strip()
            if not user_input[CONF_CHAT_MODEL]:
                errors[CONF_CHAT_MODEL] = "deployment_required"
            elif not user_input[CONF_MODEL_FAMILY]:
                errors[CONF_MODEL_FAMILY] = "model_family_required"
            elif (
                "unsupported"
                in get_capabilities(user_input[CONF_MODEL_FAMILY]).features
            ):
                errors[CONF_MODEL_FAMILY] = "model_not_supported"

        if user_input is not None and not errors:
            if user_input.get(CONF_LLM_HASS_API) is None:
                user_input.pop(CONF_LLM_HASS_API, None)

            if user_input[CONF_RECOMMENDED]:
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

            if self._subentry_type == "conversation" and CONF_PROMPT not in user_input:
                options[CONF_PROMPT] = ""
            options.update(user_input)
            if CONF_LLM_HASS_API in options and CONF_LLM_HASS_API not in user_input:
                options.pop(CONF_LLM_HASS_API)
            return await self.async_step_model()

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(step_schema), options
            ),
            errors=errors,
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage model-specific options."""
        options = self.options
        errors: dict[str, str] = {}

        response_schema: VolDictType = {
            probatio.Optional(
                CONF_MAX_TOKENS,
                default=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
            ): int,
        }
        reasoning_schema: VolDictType = {}
        tools_schema: VolDictType = {}
        web_search_schema: VolDictType = {}
        image_generation_schema: VolDictType = {}

        capabilities = get_capabilities(options[CONF_MODEL_FAMILY])

        if "code" in capabilities.features:
            tools_schema.update(
                {
                    probatio.Optional(
                        CONF_CODE_INTERPRETER,
                        default=options.get(
                            CONF_CODE_INTERPRETER, RECOMMENDED_CODE_INTERPRETER
                        ),
                    ): bool,
                }
            )
        elif CONF_CODE_INTERPRETER in options:
            options.pop(CONF_CODE_INTERPRETER)

        if reasoning_options := capabilities.reasoning:
            options[CONF_REASONING_EFFORT] = capabilities.reasoning_effort(
                options.get(CONF_REASONING_EFFORT, RECOMMENDED_REASONING_EFFORT)
            )
            reasoning_schema.update(
                {
                    probatio.Optional(
                        CONF_REASONING_EFFORT,
                        default=options[CONF_REASONING_EFFORT],
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=list(reasoning_options),
                            translation_key=CONF_REASONING_EFFORT,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_REASONING_EFFORT in options:
            options.pop(CONF_REASONING_EFFORT)

        if "pro" in capabilities.features:
            reasoning_schema.update(
                {
                    probatio.Optional(
                        CONF_PRO_MODE,
                        default=options.get(CONF_PRO_MODE, RECOMMENDED_PRO_MODE),
                    ): bool,
                }
            )
        elif CONF_PRO_MODE in options:
            options.pop(CONF_PRO_MODE)

        if "verbosity" in capabilities.features:
            response_schema.update(
                {
                    probatio.Optional(
                        CONF_VERBOSITY,
                        default=options.get(CONF_VERBOSITY, RECOMMENDED_VERBOSITY),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            translation_key=CONF_VERBOSITY,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_VERBOSITY in options:
            options.pop(CONF_VERBOSITY)

        if reasoning_summary_options := capabilities.reasoning_summary:
            stored_summary = options.get(
                CONF_REASONING_SUMMARY, RECOMMENDED_REASONING_SUMMARY
            )
            if stored_summary not in reasoning_summary_options:
                stored_summary = RECOMMENDED_REASONING_SUMMARY
                options[CONF_REASONING_SUMMARY] = stored_summary
            reasoning_schema.update(
                {
                    probatio.Optional(
                        CONF_REASONING_SUMMARY,
                        default=stored_summary,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=reasoning_summary_options,
                            translation_key=CONF_REASONING_SUMMARY,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_REASONING_SUMMARY in options:
            options.pop(CONF_REASONING_SUMMARY)

        if self._subentry_type == "conversation" and "web" in capabilities.features:
            web_search_schema.update(
                {
                    probatio.Optional(
                        CONF_WEB_SEARCH,
                        default=options.get(CONF_WEB_SEARCH, RECOMMENDED_WEB_SEARCH),
                    ): bool,
                    probatio.Optional(
                        CONF_WEB_SEARCH_CONTEXT_SIZE,
                        default=options.get(
                            CONF_WEB_SEARCH_CONTEXT_SIZE,
                            RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            translation_key=CONF_WEB_SEARCH_CONTEXT_SIZE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    probatio.Optional(
                        CONF_WEB_SEARCH_USER_LOCATION,
                        default=options.get(
                            CONF_WEB_SEARCH_USER_LOCATION,
                            RECOMMENDED_WEB_SEARCH_USER_LOCATION,
                        ),
                    ): bool,
                    probatio.Optional(
                        CONF_WEB_SEARCH_INLINE_CITATIONS,
                        default=options.get(
                            CONF_WEB_SEARCH_INLINE_CITATIONS,
                            RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS,
                        ),
                    ): bool,
                }
            )
        else:
            for key in (
                CONF_WEB_SEARCH,
                CONF_WEB_SEARCH_CONTEXT_SIZE,
                CONF_WEB_SEARCH_USER_LOCATION,
                CONF_WEB_SEARCH_CITY,
                CONF_WEB_SEARCH_REGION,
                CONF_WEB_SEARCH_COUNTRY,
                CONF_WEB_SEARCH_TIMEZONE,
                CONF_WEB_SEARCH_INLINE_CITATIONS,
            ):
                options.pop(key, None)

        if self._subentry_type == "ai_task_data" and "image" in capabilities.features:
            image_generation_schema[
                probatio.Optional(
                    CONF_IMAGE_DEPLOYMENT,
                    description={"suggested_value": options.get(CONF_IMAGE_DEPLOYMENT)},
                )
            ] = str
            image_generation_schema[
                probatio.Optional(
                    CONF_IMAGE_MODEL,
                    default=options.get(CONF_IMAGE_MODEL, RECOMMENDED_IMAGE_MODEL),
                )
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=list(IMAGE_MODEL_FAMILIES),
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            )
        else:
            options.pop(CONF_IMAGE_MODEL, None)
            options.pop(CONF_IMAGE_DEPLOYMENT, None)

        if user_input is not None:
            section_input = {
                key: value
                for section_values in user_input.values()
                for key, value in section_values.items()
            }
            _normalize_image_config(section_input, options, errors)
            if image_generation_schema and CONF_IMAGE_DEPLOYMENT not in section_input:
                options.pop(CONF_IMAGE_DEPLOYMENT, None)
            if (
                section_input.get(CONF_WEB_SEARCH)
                and section_input.get(CONF_REASONING_EFFORT) == "minimal"
            ):
                errors[CONF_WEB_SEARCH] = "web_search_minimal_reasoning"
            await self._async_apply_location_data(section_input, options, errors)
            if (
                section_input.get(CONF_CODE_INTERPRETER)
                and section_input.get(CONF_REASONING_EFFORT) == "minimal"
            ):
                errors[CONF_CODE_INTERPRETER] = "code_interpreter_minimal_reasoning"

            options.update(section_input)
            if not errors:
                return await self.async_step_sampling()

        step_schema: VolDictType = {}
        for section_name, section_schema in (
            (SECTION_RESPONSE, response_schema),
            (SECTION_REASONING, reasoning_schema),
            (SECTION_TOOLS, tools_schema),
            (SECTION_WEB_SEARCH, web_search_schema),
            (SECTION_IMAGE_GENERATION, image_generation_schema),
        ):
            if section_schema:
                step_schema[probatio.Required(section_name)] = section(
                    probatio.Schema(section_schema),
                    SectionConfig(collapsed=False),
                )

        return self.async_show_form(
            step_id="model",
            data_schema=probatio.Schema(step_schema),
            errors=errors,
        )

    async def async_step_sampling(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Offer sampling controls only after the reasoning effort is known."""
        options = self.options
        capabilities = get_capabilities(options[CONF_MODEL_FAMILY])
        if capabilities.supports_sampling(options.get(CONF_REASONING_EFFORT)):
            if user_input is None:
                return self.async_show_form(
                    step_id="sampling",
                    data_schema=self.add_suggested_values_to_schema(
                        probatio.Schema(
                            {
                                probatio.Optional(
                                    CONF_TOP_P, default=RECOMMENDED_TOP_P
                                ): NumberSelector(
                                    NumberSelectorConfig(min=0, max=1, step=0.05)
                                ),
                                probatio.Optional(
                                    CONF_TEMPERATURE, default=RECOMMENDED_TEMPERATURE
                                ): NumberSelector(
                                    NumberSelectorConfig(min=0, max=2, step=0.05)
                                ),
                            }
                        ),
                        options,
                    ),
                )
            options.update(user_input)
        else:
            options.pop(CONF_TOP_P, None)
            options.pop(CONF_TEMPERATURE, None)
        if self._is_new:
            return self.async_create_entry(title=options.pop(CONF_NAME), data=options)
        return self.async_update_and_abort(
            self._get_entry(), self._get_reconfigure_subentry(), data=options
        )

    async def _async_apply_location_data(
        self,
        section_input: dict[str, Any],
        options: dict[str, Any],
        errors: dict[str, str],
    ) -> None:
        """Keep location data only while web search requests it."""
        if (
            section_input.get(CONF_WEB_SEARCH)
            and section_input.get(CONF_WEB_SEARCH_USER_LOCATION)
            and not errors
        ):
            if error := await self._async_add_location_data(section_input):
                errors["base"] = error
            return
        for key in (
            CONF_WEB_SEARCH_CITY,
            CONF_WEB_SEARCH_REGION,
            CONF_WEB_SEARCH_COUNTRY,
            CONF_WEB_SEARCH_TIMEZONE,
        ):
            options.pop(key, None)

    async def _async_add_location_data(
        self, section_input: dict[str, Any]
    ) -> str | None:
        """Add approximate location data and return an error key on failure."""
        try:
            section_input.update(await self._get_location_data())
        except openai.AuthenticationError:
            self._get_entry().async_start_reauth(self.hass)
            return "invalid_auth"
        except openai.APIConnectionError:
            return "cannot_connect"
        except openai.RateLimitError:
            return "rate_limited"
        except json.JSONDecodeError, probatio.Invalid, openai.OpenAIError:
            return "location_lookup_failed"
        return None

    async def _get_location_data(self) -> dict[str, str]:
        """Get approximate location data of the user."""
        location_data: dict[str, str] = {}
        zone_home = self.hass.states.get(ENTITY_ID_HOME)
        if zone_home is not None:
            client = create_client(self.hass, self._get_entry().data)
            location_schema = probatio.Schema(
                {
                    probatio.Optional(
                        CONF_WEB_SEARCH_CITY,
                        description=(
                            "Free text input for the city, e.g. `San Francisco`"
                        ),
                    ): str,
                    probatio.Optional(
                        CONF_WEB_SEARCH_REGION,
                        description="Free text input for the region, e.g. `California`",
                    ): str,
                }
            )
            response = await client.responses.create(
                model=self.options[CONF_CHAT_MODEL],
                input=[
                    {
                        "role": "system",
                        "content": "Where are the following coordinates located: "
                        f"({zone_home.attributes[EntityStateAttribute.LATITUDE]},"
                        f" {zone_home.attributes[EntityStateAttribute.LONGITUDE]})?",
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "approximate_location",
                        "description": "Approximate location data of the user "
                        "for refined web search results",
                        "schema": probatio.to_openapi(
                            location_schema, openapi_version="3.1.0"
                        ),
                        "strict": False,
                    }
                },
                store=False,
            )
            location_data = location_schema(json.loads(response.output_text) or {})

        if self.hass.config.country:
            location_data[CONF_WEB_SEARCH_COUNTRY] = self.hass.config.country
        location_data[CONF_WEB_SEARCH_TIMEZONE] = self.hass.config.time_zone

        _LOGGER.debug("Location data lookup completed")

        return location_data


class OpenAISubentrySTTFlowHandler(ConfigSubentryFlow):
    """Flow for managing Azure OpenAI STT subentries."""

    options: dict[str, Any]

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        self.options = RECOMMENDED_STT_OPTIONS.copy()
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        options = self.options
        step_schema: VolDictType = {}

        if self._is_new:
            step_schema[probatio.Required(CONF_NAME, default=DEFAULT_STT_NAME)] = str

        step_schema.update(
            {
                probatio.Optional(
                    CONF_PROMPT,
                    description={
                        "suggested_value": options.get(CONF_PROMPT, DEFAULT_STT_PROMPT)
                    },
                ): TextSelector(
                    TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT)
                ),
                probatio.Required(CONF_CHAT_MODEL): probatio.All(
                    cv.string, probatio.Length(min=1)
                ),
                probatio.Required(
                    CONF_STT_MODEL,
                    description={"suggested_value": options.get(CONF_STT_MODEL)},
                ): STT_MODEL_SELECTOR,
                probatio.Optional(
                    CONF_API_VERSION,
                    description={"suggested_value": options.get(CONF_API_VERSION)},
                ): str,
            }
        )

        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_CHAT_MODEL] = user_input[CONF_CHAT_MODEL].strip()
            user_input[CONF_STT_MODEL] = user_input[CONF_STT_MODEL].strip()
            if CONF_API_VERSION in user_input:
                user_input[CONF_API_VERSION] = user_input[CONF_API_VERSION].strip()
            if not user_input[CONF_CHAT_MODEL]:
                errors[CONF_CHAT_MODEL] = "deployment_required"
            if not user_input[CONF_STT_MODEL]:
                errors[CONF_STT_MODEL] = "model_required"
            if CONF_PROMPT not in user_input:
                options[CONF_PROMPT] = ""
            if not user_input.get(CONF_API_VERSION):
                user_input.pop(CONF_API_VERSION, None)
                options.pop(CONF_API_VERSION, None)
            if not errors:
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


class OpenAISubentryTTSFlowHandler(ConfigSubentryFlow):
    """Flow for managing Azure OpenAI TTS subentries."""

    options: dict[str, Any]

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        self.options = RECOMMENDED_TTS_OPTIONS.copy()
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        options = self.options
        step_schema: VolDictType = {}

        if self._is_new:
            step_schema[probatio.Required(CONF_NAME, default=DEFAULT_TTS_NAME)] = str

        step_schema.update(
            {
                probatio.Required(CONF_CHAT_MODEL): probatio.All(
                    cv.string, probatio.Length(min=1)
                ),
                probatio.Required(
                    CONF_TTS_MODEL,
                    description={"suggested_value": options.get(CONF_TTS_MODEL)},
                ): probatio.All(TTS_MODEL_SELECTOR, probatio.Length(min=1)),
                probatio.Optional(CONF_PROMPT): TextSelector(
                    TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT)
                ),
                probatio.Optional(
                    CONF_TTS_SPEED, default=RECOMMENDED_TTS_SPEED
                ): NumberSelector(NumberSelectorConfig(min=0.25, max=4.0, step=0.01)),
            }
        )

        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input[CONF_CHAT_MODEL] = user_input[CONF_CHAT_MODEL].strip()
            user_input[CONF_TTS_MODEL] = user_input[CONF_TTS_MODEL].strip()
            if not user_input[CONF_CHAT_MODEL]:
                errors[CONF_CHAT_MODEL] = "deployment_required"
            if not user_input[CONF_TTS_MODEL]:
                errors[CONF_TTS_MODEL] = "model_required"
            if CONF_PROMPT not in user_input:
                options[CONF_PROMPT] = ""
            if not errors:
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
