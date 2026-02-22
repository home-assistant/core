"""Config flow for OpenRouter integration."""

from __future__ import annotations

import logging
from typing import Any

from openrouter import OpenRouter
from openrouter.components import Model
from openrouter.errors import OpenRouterError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)
from homeassistant.helpers.typing import VolDictType

from .const import (
    CONF_CHAT_MODEL,
    CONF_PROMPT,
    CONF_PROVIDER,
    CONF_WEB_SEARCH,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_CONVERSATION_OPTIONS,
    SECTION_MODEL,
    SECTION_OPTIONS,
    SUPPORTED_PARAMETER_STRUCTURED_OUTPUTS,
    SUPPORTED_PARAMETER_TOOLS,
)

_LOGGER = logging.getLogger(__name__)


class OpenRouterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenRouter."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {
            "conversation": ConversationFlowHandler,
            "ai_task_data": AITaskDataFlowHandler,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            api_key = user_input[CONF_API_KEY]

            def _validate_api_key():
                client = OpenRouter(api_key=api_key)
                client.api_keys.get_current_key_metadata()

            try:
                await self.hass.async_add_executor_job(_validate_api_key)
            except OpenRouterError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="OpenRouter",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )


class OpenRouterSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for OpenRouter."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.models: dict[str, Model] = {}

    async def _get_models(self) -> None:
        """Fetch models from OpenRouter."""
        entry = self._get_entry()
        api_key = entry.data[CONF_API_KEY]

        def _sync_get_models():
            client = OpenRouter(api_key=api_key)
            return client.models.list()

        response = await self.hass.async_add_executor_job(_sync_get_models)
        self.models = {model.id: model for model in response.data}

    async def _get_providers_for_model(self, model_id: str) -> list[dict[str, str]]:
        """Fetch available providers for a specific model from OpenRouter API."""
        entry = self._get_entry()
        api_key = entry.data[CONF_API_KEY]

        # Parse model_id (e.g., "anthropic/claude-3-opus")
        parts = model_id.split("/")
        if len(parts) != 2:
            _LOGGER.debug("Invalid model_id format: %s", model_id)
            return []

        author, slug = parts

        def _sync_get_providers():
            client = OpenRouter(api_key=api_key)
            return client.endpoints.list(author=author, slug=slug)

        try:
            response = await self.hass.async_add_executor_job(_sync_get_providers)

            providers = []
            for endpoint in response.data.endpoints:
                provider_name = str(endpoint.provider_name)
                provider_slug = endpoint.tag

                if provider_name and provider_slug:
                    providers.append(
                        {
                            "slug": provider_slug,
                            "name": provider_name,
                        }
                    )

            _LOGGER.debug("Found %d providers for model %s", len(providers), model_id)
        except OpenRouterError as err:
            _LOGGER.debug("Error fetching providers: %s", err)
            return []
        else:
            return providers


class ConversationFlowHandler(OpenRouterSubentryFlowHandler):
    """Handle conversation subentry flow."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self.options: dict[str, Any] = {}
        self.providers: list[dict[str, str]] = []

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

    async def validate_model_options(
        self, user_input: dict[str, Any]
    ) -> dict[str, str]:
        """Checks the selected options for errors. If there any, return them."""
        errors: dict[str, str] = {}
        # Flatten section data
        flattened_input = dict(user_input)

        # Extract data from sections
        if SECTION_MODEL in flattened_input:
            flattened_input.update(flattened_input.pop(SECTION_MODEL))
        if SECTION_OPTIONS in flattened_input:
            flattened_input.update(flattened_input.pop(SECTION_OPTIONS))

        # Convert enable_assist checkbox to LLM_HASS_API format
        if flattened_input.get("enable_assist"):
            flattened_input[CONF_LLM_HASS_API] = [llm.LLM_API_ASSIST]
        else:
            flattened_input.pop(CONF_LLM_HASS_API, None)
        flattened_input.pop("enable_assist", None)

        self.options.update(flattened_input)

        # Validate that we have a model selected
        selected_model = flattened_input.get(CONF_CHAT_MODEL)
        if not selected_model:
            errors[SECTION_MODEL] = "model_required"
        if selected_model not in self.models:
            errors[SECTION_MODEL] = "invalid_model_selected"

        # Validate tool support when assist is enabled
        enable_assist = CONF_LLM_HASS_API in flattened_input
        if enable_assist and selected_model and selected_model in self.models:
            model = self.models[selected_model]
            if SUPPORTED_PARAMETER_TOOLS not in model.supported_parameters:
                errors[SECTION_MODEL] = "model_no_tool_support"

        return errors

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage conversation agent configuration - step 1: basic options."""
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        errors: dict[str, str] = {}

        try:
            await self._get_models()
        except OpenRouterError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        if user_input is not None:
            errors = await self.validate_model_options(user_input)
            if not errors:
                # Move to provider selection step
                return await self.async_step_providers()

        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]

        if suggested_llm_apis := self.options.get(CONF_LLM_HASS_API):
            if isinstance(suggested_llm_apis, str):
                suggested_llm_apis = [suggested_llm_apis]
            valid_api_ids = {api["value"] for api in hass_apis}
            self.options[CONF_LLM_HASS_API] = [
                api for api in suggested_llm_apis if api in valid_api_ids
            ]

        # Get current model selection
        current_model = self.options.get(CONF_CHAT_MODEL)

        model_options = [
            SelectOptionDict(value=model.id, label=model.name)
            for model in sorted(self.models.values(), key=lambda m: m.name)
        ]

        step_schema: VolDictType = {}

        if self._is_new:
            step_schema[vol.Required(CONF_NAME, default=DEFAULT_CONVERSATION_NAME)] = (
                str
            )

        step_schema[
            vol.Optional(
                CONF_PROMPT,
                description={
                    "suggested_value": self.options.get(
                        CONF_PROMPT, RECOMMENDED_CONVERSATION_OPTIONS[CONF_PROMPT]
                    )
                },
            )
        ] = TemplateSelector()

        step_schema[SECTION_MODEL] = section(
            vol.Schema(
                {
                    vol.Required(
                        CONF_CHAT_MODEL,
                        default=current_model,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=model_options,
                            mode=SelectSelectorMode.DROPDOWN,
                            sort=True,
                            custom_value=True,
                        ),
                    ),
                }
            ),
        )

        step_schema[SECTION_OPTIONS] = section(
            vol.Schema(
                {
                    vol.Optional(
                        "enable_assist",
                        default=bool(self.options.get(CONF_LLM_HASS_API, [])),
                    ): bool,
                    vol.Optional(
                        CONF_WEB_SEARCH,
                        default=self.options.get(
                            CONF_WEB_SEARCH,
                            RECOMMENDED_CONVERSATION_OPTIONS[CONF_WEB_SEARCH],
                        ),
                    ): bool,
                }
            ),
        )

        # Call init step one more time for validation
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), self.options
            ),
            errors=errors,
            last_step=False,
        )

    async def async_step_providers(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage provider selection - step 2."""
        if user_input is not None:
            self.options.update(user_input)

            if self._is_new:
                return self.async_create_entry(
                    title=self.options[CONF_NAME],
                    data=self.options,
                )
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=self.options,
            )

        # Fetch providers for the selected model
        selected_model = self.options.get(CONF_CHAT_MODEL)

        _LOGGER.debug("Fetching providers for model: %s", selected_model)
        _LOGGER.debug("Available models: %s", list(self.models.keys()))

        if selected_model and selected_model in self.models:
            self.providers = await self._get_providers_for_model(selected_model)
            _LOGGER.debug(
                "Found %d providers for model %s", len(self.providers), selected_model
            )
        else:
            _LOGGER.debug("Model %s not found in models list", selected_model)

        provider_options = [
            SelectOptionDict(value=provider["slug"], label=provider["name"])
            for provider in self.providers
        ]

        step_schema: VolDictType = {
            vol.Optional(
                CONF_PROVIDER,
                default=self.options.get(CONF_PROVIDER, []),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=provider_options,
                    multiple=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }

        return self.async_show_form(
            step_id="providers",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), self.options
            ),
            last_step=True,
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
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            if self._is_new:
                return self.async_create_entry(
                    title=self.models[user_input[CONF_CHAT_MODEL]].name,
                    data=user_input,
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
            if SUPPORTED_PARAMETER_STRUCTURED_OUTPUTS in model.supported_parameters
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CHAT_MODEL,
                        default=self.options.get(CONF_CHAT_MODEL),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN, sort=True
                        ),
                    ),
                }
            ),
        )
