"""Config flow for Ollama integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
import sys
from typing import Any

import httpx
import ollama
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LLM_HASS_API, CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util.ssl import get_default_context

from . import OllamaConfigEntry
from .const import (
    CONF_KEEP_ALIVE,
    CONF_MAX_HISTORY,
    CONF_MODEL,
    CONF_NUM_CTX,
    CONF_PROMPT,
    CONF_THINK,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_KEEP_ALIVE,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MODEL,
    DEFAULT_NUM_CTX,
    DEFAULT_THINK,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MAX_NUM_CTX,
    MIN_NUM_CTX,
    MODEL_NAMES,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
    }
)


class OllamaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ollama."""

    VERSION = 3
    MINOR_VERSION = 3

    def __init__(self) -> None:
        """Initialize config flow."""
        self.url: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        url = user_input[CONF_URL]

        self._async_abort_entries_match({CONF_URL: url})

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
            )

        try:
            client = ollama.AsyncClient(host=url, verify=get_default_context())
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                await client.list()
        except (TimeoutError, httpx.ConnectError):
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, user_input
                ),
                errors=errors,
            )

        return self.async_create_entry(
            title=url,
            data={CONF_URL: url},
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "conversation": OllamaSubentryFlowHandler,
            "ai_task_data": OllamaSubentryFlowHandler,
        }


class OllamaSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing Ollama subentries."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self._name: str | None = None
        self._model: str | None = None
        self.download_task: asyncio.Task | None = None
        self._config_data: dict[str, Any] | None = None

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    @property
    def _client(self) -> ollama.AsyncClient:
        """Return the Ollama client."""
        entry: OllamaConfigEntry = self._get_entry()
        return entry.runtime_data

    async def async_step_set_options(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle model selection and configuration step."""
        if self._get_entry().state != ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is None:
            # Get available models from Ollama server
            try:
                async with asyncio.timeout(DEFAULT_TIMEOUT):
                    response = await self._client.list()

                downloaded_models: set[str] = {
                    model_info["model"] for model_info in response.get("models", [])
                }
            except (TimeoutError, httpx.ConnectError, httpx.HTTPError):
                _LOGGER.exception("Failed to get models from Ollama server")
                return self.async_abort(reason="cannot_connect")

            # Show models that have been downloaded first, followed by all known
            # models (only latest tags).
            models_to_list = [
                SelectOptionDict(label=f"{m} (downloaded)", value=m)
                for m in sorted(downloaded_models)
            ] + [
                SelectOptionDict(label=m, value=f"{m}:latest")
                for m in sorted(MODEL_NAMES)
                if m not in downloaded_models
            ]

            if self._is_new:
                options = {}
            else:
                options = self._get_reconfigure_subentry().data.copy()

            return self.async_show_form(
                step_id="set_options",
                data_schema=vol.Schema(
                    ollama_config_option_schema(
                        self.hass,
                        self._is_new,
                        self._subentry_type,
                        options,
                        models_to_list,
                    )
                ),
            )

        self._model = user_input[CONF_MODEL]
        if self._is_new:
            self._name = user_input.pop(CONF_NAME)

        # Check if model needs to be downloaded
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self._client.list()

            currently_downloaded_models: set[str] = {
                model_info["model"] for model_info in response.get("models", [])
            }

            if self._model not in currently_downloaded_models:
                # Store the user input to use after download
                self._config_data = user_input
                # Ollama server needs to download model first
                return await self.async_step_download()
        except Exception:
            _LOGGER.exception("Failed to check model availability")
            return self.async_abort(reason="cannot_connect")

        # Model is already downloaded, create/update the entry
        if self._is_new:
            return self.async_create_entry(
                title=self._name,
                data=user_input,
            )

        return self.async_update_and_abort(
            self._get_entry(),
            self._get_reconfigure_subentry(),
            data=user_input,
        )

    async def async_step_download(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Step to wait for Ollama server to download a model."""
        assert self._model is not None

        if self.download_task is None:
            # Tell Ollama server to pull the model.
            # The task will block until the model and metadata are fully
            # downloaded.
            self.download_task = self.hass.async_create_background_task(
                self._client.pull(self._model),
                f"Downloading {self._model}",
            )

        if self.download_task.done():
            if err := self.download_task.exception():
                _LOGGER.exception("Unexpected error while downloading model: %s", err)
                return self.async_show_progress_done(next_step_id="failed")

            return self.async_show_progress_done(next_step_id="finish")

        return self.async_show_progress(
            step_id="download",
            progress_action="download",
            progress_task=self.download_task,
        )

    async def async_step_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Step after model downloading has failed."""
        return self.async_abort(reason="download_failed")

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Step after model downloading has succeeded."""
        assert self._config_data is not None

        # Model download completed, create/update the entry with stored config
        if self._is_new:
            return self.async_create_entry(
                title=self._name,
                data=self._config_data,
            )
        return self.async_update_and_abort(
            self._get_entry(),
            self._get_reconfigure_subentry(),
            data=self._config_data,
        )

    async_step_user = async_step_set_options
    async_step_reconfigure = async_step_set_options


def filter_invalid_llm_apis(hass: HomeAssistant, selected_apis: list[str]) -> list[str]:
    """Accepts a list of LLM API IDs and filters this against those currently available."""

    valid_llm_apis = [api.id for api in llm.async_get_apis(hass)]

    return [api for api in selected_apis if api in valid_llm_apis]


def ollama_config_option_schema(
    hass: HomeAssistant,
    is_new: bool,
    subentry_type: str,
    options: Mapping[str, Any],
    models_to_list: list[SelectOptionDict],
) -> dict:
    """Ollama options schema."""
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

    selected_llm_apis = filter_invalid_llm_apis(
        hass, options.get(CONF_LLM_HASS_API, [])
    )

    schema.update(
        {
            vol.Required(
                CONF_MODEL,
                description={"suggested_value": options.get(CONF_MODEL, DEFAULT_MODEL)},
            ): SelectSelector(
                SelectSelectorConfig(options=models_to_list, custom_value=True)
            ),
        }
    )
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
                    description={"suggested_value": selected_llm_apis},
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                label=api.name,
                                value=api.id,
                            )
                            for api in llm.async_get_apis(hass)
                        ],
                        multiple=True,
                    )
                ),
            }
        )
    schema.update(
        {
            vol.Optional(
                CONF_NUM_CTX,
                description={
                    "suggested_value": options.get(CONF_NUM_CTX, DEFAULT_NUM_CTX)
                },
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_NUM_CTX,
                    max=MAX_NUM_CTX,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_MAX_HISTORY,
                description={
                    "suggested_value": options.get(
                        CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY
                    )
                },
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=sys.maxsize, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_KEEP_ALIVE,
                description={
                    "suggested_value": options.get(CONF_KEEP_ALIVE, DEFAULT_KEEP_ALIVE)
                },
            ): NumberSelector(
                NumberSelectorConfig(
                    min=-1, max=sys.maxsize, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_THINK,
                description={
                    "suggested_value": options.get("think", DEFAULT_THINK),
                },
            ): BooleanSelector(),
        }
    )

    return schema
