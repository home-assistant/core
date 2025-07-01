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
from homeassistant.helpers import llm
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

from .const import (
    CONF_KEEP_ALIVE,
    CONF_MAX_HISTORY,
    CONF_MODEL,
    CONF_NUM_CTX,
    CONF_PROMPT,
    CONF_THINK,
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

    VERSION = 2
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize config flow."""
        self.url: str | None = None
        self.model: str | None = None
        self.client: ollama.AsyncClient | None = None
        self.download_task: asyncio.Task | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        user_input = user_input or {}
        self.url = user_input.get(CONF_URL, self.url)
        self.model = user_input.get(CONF_MODEL, self.model)

        if self.url is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, last_step=False
            )

        errors = {}

        self._async_abort_entries_match({CONF_URL: self.url})

        try:
            self.client = ollama.AsyncClient(
                host=self.url, verify=get_default_context()
            )
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.client.list()

            downloaded_models: set[str] = {
                model_info["model"] for model_info in response.get("models", [])
            }
        except (TimeoutError, httpx.ConnectError):
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        if self.model is None:
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
            model_step_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL, description={"suggested_value": DEFAULT_MODEL}
                    ): SelectSelector(
                        SelectSelectorConfig(options=models_to_list, custom_value=True)
                    ),
                }
            )

            return self.async_show_form(
                step_id="user",
                data_schema=model_step_schema,
            )

        if self.model not in downloaded_models:
            # Ollama server needs to download model first
            return await self.async_step_download()

        return self.async_create_entry(
            title=self.url,
            data={CONF_URL: self.url, CONF_MODEL: self.model},
            subentries=[
                {
                    "subentry_type": "conversation",
                    "data": {},
                    "title": _get_title(self.model),
                    "unique_id": None,
                }
            ],
        )

    async def async_step_download(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to wait for Ollama server to download a model."""
        assert self.model is not None
        assert self.client is not None

        if self.download_task is None:
            # Tell Ollama server to pull the model.
            # The task will block until the model and metadata are fully
            # downloaded.
            self.download_task = self.hass.async_create_background_task(
                self.client.pull(self.model),
                f"Downloading {self.model}",
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

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step after model downloading has succeeded."""
        assert self.url is not None
        assert self.model is not None

        return self.async_create_entry(
            title=_get_title(self.model),
            data={CONF_URL: self.url, CONF_MODEL: self.model},
            subentries=[
                {
                    "subentry_type": "conversation",
                    "data": {},
                    "title": _get_title(self.model),
                    "unique_id": None,
                }
            ],
        )

    async def async_step_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step after model downloading has failed."""
        return self.async_abort(reason="download_failed")

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"conversation": ConversationSubentryFlowHandler}


class ConversationSubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing conversation subentries."""

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
                options = {}
            else:
                options = self._get_reconfigure_subentry().data.copy()

        elif self._is_new:
            return self.async_create_entry(
                title=user_input.pop(CONF_NAME),
                data=user_input,
            )
        else:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=user_input,
            )

        schema = ollama_config_option_schema(self.hass, self._is_new, options)
        return self.async_show_form(
            step_id="set_options", data_schema=vol.Schema(schema), errors=errors
        )

    async_step_user = async_step_set_options
    async_step_reconfigure = async_step_set_options


def ollama_config_option_schema(
    hass: HomeAssistant, is_new: bool, options: Mapping[str, Any]
) -> dict:
    """Ollama options schema."""
    hass_apis: list[SelectOptionDict] = [
        SelectOptionDict(
            label=api.name,
            value=api.id,
        )
        for api in llm.async_get_apis(hass)
    ]

    if is_new:
        schema: dict[vol.Required | vol.Optional, Any] = {
            vol.Required(CONF_NAME, default="Ollama Conversation"): str,
        }
    else:
        schema = {}

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
                description={"suggested_value": options.get(CONF_LLM_HASS_API)},
            ): SelectSelector(SelectSelectorConfig(options=hass_apis, multiple=True)),
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


def _get_title(model: str) -> str:
    """Get title for config entry."""
    if model.endswith(":latest"):
        model = model.split(":", maxsplit=1)[0]

    return model
