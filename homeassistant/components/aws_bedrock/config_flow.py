"""Config flow for AWS Bedrock integration."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LLM_HASS_API, CONF_NAME
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

from .const import (
    AVAILABLE_MODELS,
    AVAILABLE_REGIONS,
    CONF_ACCESS_KEY_ID,
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    CONF_TEMPERATURE,
    DEFAULT,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    LOGGER,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): str,
        vol.Required(CONF_SECRET_ACCESS_KEY): str,
        vol.Optional(CONF_REGION, default=DEFAULT[CONF_REGION]): vol.In(
            AVAILABLE_REGIONS
        ),
    }
)

DEFAULT_CONVERSATION_OPTIONS = {
    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
    CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_CHAT_MODEL: DEFAULT[CONF_CHAT_MODEL],
    CONF_MAX_TOKENS: DEFAULT[CONF_MAX_TOKENS],
    CONF_TEMPERATURE: DEFAULT[CONF_TEMPERATURE],
}

DEFAULT_AI_TASK_OPTIONS = {
    CONF_CHAT_MODEL: DEFAULT[CONF_CHAT_MODEL],
    CONF_MAX_TOKENS: DEFAULT[CONF_MAX_TOKENS],
    CONF_TEMPERATURE: DEFAULT[CONF_TEMPERATURE],
}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    def test_connection() -> None:
        """Test AWS Bedrock connection."""
        bedrock_client = boto3.client(
            "bedrock",
            aws_access_key_id=data[CONF_ACCESS_KEY_ID],
            aws_secret_access_key=data[CONF_SECRET_ACCESS_KEY],
            region_name=data.get(CONF_REGION, DEFAULT[CONF_REGION]),
        )
        bedrock_client.list_foundation_models(byOutputModality="TEXT")

    await hass.async_add_executor_job(test_connection)


class AWSBedrockConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AWS Bedrock."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured with same credentials
            await self.async_set_unique_id(
                f"{user_input[CONF_ACCESS_KEY_ID]}_{user_input.get(CONF_REGION, DEFAULT[CONF_REGION])}"
            )
            self._abort_if_unique_id_configured()

            try:
                await validate_input(self.hass, user_input)
            except ClientError as err:
                error_code = err.response.get("Error", {}).get("Code", "")
                if error_code in (
                    "InvalidSignatureException",
                    "UnrecognizedClientException",
                ):
                    errors["base"] = "invalid_auth"
                else:
                    LOGGER.exception("Unexpected AWS error")
                    errors["base"] = "cannot_connect"
            except BotoCoreError:
                LOGGER.exception("Cannot connect to AWS Bedrock")
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"AWS Bedrock ({user_input.get(CONF_REGION, DEFAULT[CONF_REGION])})",
                    data=user_input,
                    subentries=[
                        {
                            "subentry_type": "conversation",
                            "data": DEFAULT_CONVERSATION_OPTIONS,
                            "title": DEFAULT_CONVERSATION_NAME,
                            "unique_id": None,
                        },
                        {
                            "subentry_type": "ai_task_data",
                            "data": DEFAULT_AI_TASK_OPTIONS,
                            "title": DEFAULT_AI_TASK_NAME,
                            "unique_id": None,
                        },
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
        return {
            "conversation": ConversationSubentryFlowHandler,
            "ai_task_data": ConversationSubentryFlowHandler,
        }


class ConversationSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing conversation subentries."""

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
            self.options = DEFAULT_AI_TASK_OPTIONS.copy()
        else:
            self.options = DEFAULT_CONVERSATION_OPTIONS.copy()
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
        """Set initial options."""
        # abort if entry is not loaded
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        step_schema: VolDictType = {}

        if self._is_new:
            if self._subentry_type == "ai_task_data":
                default_name = DEFAULT_AI_TASK_NAME
            else:
                default_name = DEFAULT_CONVERSATION_NAME
            step_schema[vol.Required(CONF_NAME, default=default_name)] = str

        if self._subentry_type == "conversation":
            step_schema.update(
                {
                    vol.Optional(CONF_PROMPT): TemplateSelector(),
                }
            )

        # Use hardcoded Nova models
        available_models = AVAILABLE_MODELS

        # Build model selector options
        model_options = [
            SelectOptionDict(
                label=f"{model['name']} ({model['id']})",
                value=model["id"],
            )
            for model in available_models
        ]

        # Model configuration
        step_schema[
            vol.Optional(
                CONF_CHAT_MODEL,
                default=self.options.get(CONF_CHAT_MODEL, DEFAULT[CONF_CHAT_MODEL]),
            )
        ] = SelectSelector(
            SelectSelectorConfig(
                options=model_options,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        step_schema[
            vol.Optional(
                CONF_MAX_TOKENS,
                default=self.options.get(CONF_MAX_TOKENS, DEFAULT[CONF_MAX_TOKENS]),
            )
        ] = int
        step_schema[
            vol.Optional(
                CONF_TEMPERATURE,
                default=self.options.get(CONF_TEMPERATURE, DEFAULT[CONF_TEMPERATURE]),
            )
        ] = NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05))

        if user_input is not None:
            # Set llm_hass_api for conversation agents
            if self._subentry_type == "conversation":
                user_input[CONF_LLM_HASS_API] = [llm.LLM_API_ASSIST]

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

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(step_schema), self.options
            ),
            last_step=True,
        )
