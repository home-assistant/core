"""Config flow for Anthropic integration."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
import logging
from typing import Any, cast

import anthropic
import voluptuous as vol

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
    TemplateSelector,
)

from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    CONF_THINKING_BUDGET,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_THINKING_BUDGET,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

RECOMMENDED_OPTIONS = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = await hass.async_add_executor_job(
        partial(anthropic.AsyncAnthropic, api_key=data[CONF_API_KEY])
    )
    await client.models.list(timeout=10.0)


class AnthropicConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anthropic."""

    VERSION = 2
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                await validate_input(self.hass, user_input)
            except anthropic.APITimeoutError:
                errors["base"] = "timeout_connect"
            except anthropic.APIConnectionError:
                errors["base"] = "cannot_connect"
            except anthropic.APIStatusError as e:
                errors["base"] = "unknown"
                if (
                    isinstance(e.body, dict)
                    and (error := e.body.get("error"))
                    and error.get("type") == "authentication_error"
                ):
                    errors["base"] = "authentication_error"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Claude",
                    data=user_input,
                    subentries=[
                        {
                            "subentry_type": "conversation",
                            "data": RECOMMENDED_OPTIONS,
                            "title": DEFAULT_CONVERSATION_NAME,
                            "unique_id": None,
                        }
                    ],
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors or None
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"conversation": ConversationSubentryFlowHandler}


class ConversationSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing conversation subentries."""

    last_rendered_recommended = False

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
                options = RECOMMENDED_OPTIONS.copy()
            else:
                # If this is a reconfiguration, we need to copy the existing options
                # so that we can show the current values in the form.
                options = self._get_reconfigure_subentry().data.copy()

            self.last_rendered_recommended = cast(
                bool, options.get(CONF_RECOMMENDED, False)
            )

        elif user_input[CONF_RECOMMENDED] == self.last_rendered_recommended:
            if not user_input.get(CONF_LLM_HASS_API):
                user_input.pop(CONF_LLM_HASS_API, None)
            if user_input.get(
                CONF_THINKING_BUDGET, RECOMMENDED_THINKING_BUDGET
            ) >= user_input.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS):
                errors[CONF_THINKING_BUDGET] = "thinking_budget_too_large"

            if not errors:
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

            options = user_input
            self.last_rendered_recommended = user_input[CONF_RECOMMENDED]
        else:
            # Re-render the options again, now with the recommended options shown/hidden
            self.last_rendered_recommended = user_input[CONF_RECOMMENDED]

            options = {
                CONF_RECOMMENDED: user_input[CONF_RECOMMENDED],
                CONF_PROMPT: user_input[CONF_PROMPT],
                CONF_LLM_HASS_API: user_input.get(CONF_LLM_HASS_API),
            }

        suggested_values = options.copy()
        if not suggested_values.get(CONF_PROMPT):
            suggested_values[CONF_PROMPT] = llm.DEFAULT_INSTRUCTIONS_PROMPT
        if (
            suggested_llm_apis := suggested_values.get(CONF_LLM_HASS_API)
        ) and isinstance(suggested_llm_apis, str):
            suggested_values[CONF_LLM_HASS_API] = [suggested_llm_apis]

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                anthropic_config_option_schema(self.hass, self._is_new, options)
            ),
            suggested_values,
        )

        return self.async_show_form(
            step_id="set_options",
            data_schema=schema,
            errors=errors or None,
        )

    async_step_user = async_step_set_options
    async_step_reconfigure = async_step_set_options


def anthropic_config_option_schema(
    hass: HomeAssistant,
    is_new: bool,
    options: Mapping[str, Any],
) -> dict:
    """Return a schema for Anthropic completion options."""
    hass_apis: list[SelectOptionDict] = [
        SelectOptionDict(
            label=api.name,
            value=api.id,
        )
        for api in llm.async_get_apis(hass)
    ]

    if is_new:
        schema: dict[vol.Required | vol.Optional, Any] = {
            vol.Required(CONF_NAME, default=DEFAULT_CONVERSATION_NAME): str,
        }
    else:
        schema = {}

    schema.update(
        {
            vol.Optional(CONF_PROMPT): TemplateSelector(),
            vol.Optional(
                CONF_LLM_HASS_API,
            ): SelectSelector(SelectSelectorConfig(options=hass_apis, multiple=True)),
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
                CONF_CHAT_MODEL,
                default=RECOMMENDED_CHAT_MODEL,
            ): str,
            vol.Optional(
                CONF_MAX_TOKENS,
                default=RECOMMENDED_MAX_TOKENS,
            ): int,
            vol.Optional(
                CONF_TEMPERATURE,
                default=RECOMMENDED_TEMPERATURE,
            ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
            vol.Optional(
                CONF_THINKING_BUDGET,
                default=RECOMMENDED_THINKING_BUDGET,
            ): int,
        }
    )
    return schema
