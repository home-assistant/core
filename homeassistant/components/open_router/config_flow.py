"""Config flow for OpenRouter integration."""

from __future__ import annotations

import logging
from typing import Any

from python_open_router import (
    Model,
    OpenRouterClient,
    OpenRouterError,
    SupportedParameter,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
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

from .const import CONF_PROMPT, DOMAIN, RECOMMENDED_CONVERSATION_OPTIONS

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
            client = OpenRouterClient(
                user_input[CONF_API_KEY], async_get_clientsession(self.hass)
            )
            try:
                await client.get_key_data()
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
        client = OpenRouterClient(
            entry.data[CONF_API_KEY], async_get_clientsession(self.hass)
        )
        try:
            models = await client.get_models()
            self.models = {model.id: model for model in models}
        except ValueError as e:
            # Handle parsing errors for new model architectures/modalities
            _LOGGER.warning("Error parsing some models, retrying with safe parsing: %s", e)
            # Try to get raw response and parse safely
            try:
                import aiohttp
                session = async_get_clientsession(self.hass)
                headers = {"Authorization": f"Bearer {entry.data[CONF_API_KEY]}"}
                async with session.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=headers
                ) as resp:
                    data = await resp.json()
                    self.models = {}
                    for model_data in data.get("data", []):
                        try:
                            # Create minimal model object
                            model = type('Model', (), {
                                'id': model_data.get('id', 'unknown'),
                                'name': model_data.get('name', model_data.get('id', 'Unknown')),
                                'supported_parameters': []
                            })()
                            self.models[model.id] = model
                        except Exception as model_err:
                            _LOGGER.debug("Skipping model %s: %s", model_data.get('id'), model_err)
            except Exception:
                # If safe parsing also fails, re-raise original error
                raise


class ConversationFlowHandler(OpenRouterSubentryFlowHandler):
    """Handle subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create a sensor subentry."""
        if user_input is not None:
            if not user_input.get(CONF_LLM_HASS_API):
                user_input.pop(CONF_LLM_HASS_API, None)
            return self.async_create_entry(
                title=self.models[user_input[CONF_MODEL]].name, data=user_input
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
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN, sort=True
                        ),
                    ),
                    vol.Optional(
                        CONF_PROMPT,
                        description={
                            "suggested_value": RECOMMENDED_CONVERSATION_OPTIONS[
                                CONF_PROMPT
                            ]
                        },
                    ): TemplateSelector(),
                    vol.Optional(
                        CONF_LLM_HASS_API,
                        default=RECOMMENDED_CONVERSATION_OPTIONS[CONF_LLM_HASS_API],
                    ): SelectSelector(
                        SelectSelectorConfig(options=hass_apis, multiple=True)
                    ),
                }
            ),
        )


class AITaskDataFlowHandler(OpenRouterSubentryFlowHandler):
    """Handle subentry flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create a sensor subentry."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.models[user_input[CONF_MODEL]].name, data=user_input
            )
        try:
            await self._get_models()
        except OpenRouterError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")
        # Include all models for AI tasks, but prioritize structured output models
        options = []
        structured_models = []
        other_models = []
        
        for model in self.models.values():
            option = SelectOptionDict(value=model.id, label=model.name)
            if SupportedParameter.STRUCTURED_OUTPUTS in model.supported_parameters:
                structured_models.append(option)
            else:
                # Include vision models even without structured output support
                # This allows Claude-3, GPT-4V, etc. to be used for image analysis
                other_models.append(option)
        
        # Structured output models first, then others
        options = structured_models + other_models
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN, sort=True
                        ),
                    ),
                }
            ),
        )
