"""Config flow for LM Studio integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import LMStudioConfigEntry
from .client import (
    LMStudioAuthError,
    LMStudioClient,
    LMStudioConnectionError,
    LMStudioResponseError,
)
from .const import (
    CONF_CONTEXT_LENGTH,
    CONF_MAX_HISTORY,
    CONF_MAX_OUTPUT_TOKENS,
    CONF_MIN_P,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_REASONING,
    CONF_REPEAT_PENALTY,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_MAX_HISTORY,
    DEFAULT_TIMEOUT,
    DOMAIN,
    REASONING_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Optional(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    client = LMStudioClient(
        hass=hass,
        base_url=data[CONF_URL],
        api_key=data.get(CONF_API_KEY),
        timeout=DEFAULT_TIMEOUT,
    )
    await client.async_list_models()


class LMStudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LM Studio."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL]
            try:
                url = cv.url(url)
            except vol.Invalid:
                errors["base"] = "invalid_url"
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.add_suggested_values_to_schema(
                        STEP_USER_DATA_SCHEMA, user_input
                    ),
                    errors=errors,
                    description_placeholders={
                        "default_url": "http://localhost:1234",
                    },
                )

            user_input[CONF_URL] = url
            if self.source != SOURCE_REAUTH:
                self._async_abort_entries_match({CONF_URL: url})

            try:
                await _validate_input(self.hass, user_input)
            except LMStudioAuthError:
                errors["base"] = "invalid_auth"
            except LMStudioConnectionError:
                errors["base"] = "cannot_connect"
            except LMStudioResponseError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )
                return self.async_create_entry(
                    title=url,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "default_url": "http://localhost:1234",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth details."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "default_url": "http://localhost:1234",
                },
            )

        return await self.async_step_user(user_input)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "conversation": LMStudioSubentryFlowHandler,
            "ai_task_data": LMStudioSubentryFlowHandler,
        }


class LMStudioSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing LM Studio subentries."""

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == SOURCE_USER

    @property
    def _client(self) -> LMStudioClient:
        """Return the LM Studio client."""
        entry: LMStudioConfigEntry = self._get_entry()
        return entry.runtime_data.client

    async def async_step_set_options(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle model selection and configuration step."""
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is None:
            try:
                models = await self._client.async_list_models()
            except LMStudioAuthError, LMStudioConnectionError, LMStudioResponseError:
                _LOGGER.exception("Failed to get models from server")
                return self.async_abort(reason="cannot_connect")

            model_options = _build_model_options(models)

            if self._is_new:
                options: dict[str, Any] = {}
            else:
                options = self._get_reconfigure_subentry().data.copy()

            return self.async_show_form(
                step_id="set_options",
                data_schema=vol.Schema(
                    lmstudio_config_option_schema(
                        self.hass,
                        self._is_new,
                        self._subentry_type,
                        options,
                        model_options,
                    )
                ),
            )

        if self._is_new:
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(title=name, data=user_input)

        return self.async_update_and_abort(
            self._get_entry(),
            self._get_reconfigure_subentry(),
            data=user_input,
        )

    async_step_user = async_step_set_options
    async_step_reconfigure = async_step_set_options


def _build_model_options(models: list[dict[str, Any]]) -> list[SelectOptionDict]:
    """Return model options for the selector."""
    options: list[SelectOptionDict] = []

    for model in models:
        key = model.get("key")
        if not isinstance(key, str):
            continue
        model_type = model.get("type")
        if model_type not in (None, "llm"):
            continue
        display_name = model.get("display_name")
        if not isinstance(display_name, str):
            display_name = key
        label = display_name if display_name == key else f"{display_name} ({key})"
        options.append(SelectOptionDict(label=label, value=key))

    options.sort(key=lambda option: option["label"].lower())
    return options


def lmstudio_config_option_schema(
    hass: HomeAssistant,
    is_new: bool,
    subentry_type: str,
    options: Mapping[str, Any],
    models_to_list: list[SelectOptionDict],
) -> dict:
    """LM Studio options schema."""
    if is_new:
        if subentry_type == "ai_task_data":
            default_name = DEFAULT_AI_TASK_NAME
        else:
            default_name = DEFAULT_CONVERSATION_NAME

        schema: dict = {
            vol.Required(CONF_NAME, default=default_name): str,
        }
    else:
        schema = {}

    schema.update(
        {
            vol.Required(
                CONF_MODEL,
                description={"suggested_value": options.get(CONF_MODEL)},
            ): SelectSelector(
                SelectSelectorConfig(
                    options=models_to_list,
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            ),
        }
    )

    if subentry_type == "conversation":
        schema.update(
            {
                vol.Optional(
                    CONF_PROMPT,
                    description={"suggested_value": options.get(CONF_PROMPT)},
                ): TemplateSelector(),
                vol.Optional(
                    CONF_MAX_HISTORY,
                    description={
                        "suggested_value": options.get(
                            CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY
                        )
                    },
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=2**31 - 1, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )

    schema.update(
        {
            vol.Optional(
                CONF_MAX_OUTPUT_TOKENS,
                description={"suggested_value": options.get(CONF_MAX_OUTPUT_TOKENS)},
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=2**31 - 1, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_TEMPERATURE,
                description={"suggested_value": options.get(CONF_TEMPERATURE)},
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.0, max=1.0, step=0.01, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_TOP_P,
                description={"suggested_value": options.get(CONF_TOP_P)},
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.0, max=1.0, step=0.01, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_TOP_K,
                description={"suggested_value": options.get(CONF_TOP_K)},
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=2**31 - 1, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_MIN_P,
                description={"suggested_value": options.get(CONF_MIN_P)},
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.0, max=1.0, step=0.01, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_REPEAT_PENALTY,
                description={"suggested_value": options.get(CONF_REPEAT_PENALTY)},
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0.0, max=2.0, step=0.01, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_CONTEXT_LENGTH,
                description={"suggested_value": options.get(CONF_CONTEXT_LENGTH)},
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=2**31 - 1, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_REASONING,
                description={"suggested_value": options.get(CONF_REASONING)},
            ): SelectSelector(SelectSelectorConfig(options=list(REASONING_OPTIONS))),
        }
    )

    return schema
