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
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LLM_HASS_API, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
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
    DEFAULT_KEEP_ALIVE,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MODEL,
    DEFAULT_NUM_CTX,
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

    VERSION = 1

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
            title=_get_title(self.model),
            data={CONF_URL: self.url, CONF_MODEL: self.model},
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
        )

    async def async_step_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step after model downloading has failed."""
        return self.async_abort(reason="download_failed")

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return OllamaOptionsFlow(config_entry)


class OllamaOptionsFlow(OptionsFlow):
    """Ollama options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.url: str = config_entry.data[CONF_URL]
        self.model: str = config_entry.data[CONF_MODEL]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title=_get_title(self.model), data=user_input
            )

        options: Mapping[str, Any] = self.config_entry.options or {}
        schema = ollama_config_option_schema(self.hass, options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )


def ollama_config_option_schema(
    hass: HomeAssistant, options: Mapping[str, Any]
) -> dict:
    """Ollama options schema."""
    hass_apis: list[SelectOptionDict] = [
        SelectOptionDict(
            label=api.name,
            value=api.id,
        )
        for api in llm.async_get_apis(hass)
    ]

    return {
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
            description={"suggested_value": options.get(CONF_NUM_CTX, DEFAULT_NUM_CTX)},
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_NUM_CTX, max=MAX_NUM_CTX, step=1, mode=NumberSelectorMode.BOX
            )
        ),
        vol.Optional(
            CONF_MAX_HISTORY,
            description={
                "suggested_value": options.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY)
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
    }


def _get_title(model: str) -> str:
    """Get title for config entry."""
    if model.endswith(":latest"):
        model = model.split(":", maxsplit=1)[0]

    return model
