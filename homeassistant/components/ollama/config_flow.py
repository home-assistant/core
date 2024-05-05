"""Config flow for Ollama integration."""

from __future__ import annotations

import asyncio
import logging
import sys
from types import MappingProxyType
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
from homeassistant.const import CONF_URL
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

from .const import (
    CONF_MAX_HISTORY,
    CONF_MODEL,
    CONF_PROMPT,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    DOMAIN,
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
            self.client = ollama.AsyncClient(host=self.url)
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self.client.list()

            downloaded_models: set[str] = {
                model_info["model"] for model_info in response.get("models", [])
            }
        except (TimeoutError, httpx.ConnectError):
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
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
        self.config_entry = config_entry
        self.url: str = self.config_entry.data[CONF_URL]
        self.model: str = self.config_entry.data[CONF_MODEL]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title=_get_title(self.model), data=user_input
            )

        options = self.config_entry.options or MappingProxyType({})
        schema = ollama_config_option_schema(options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )


def ollama_config_option_schema(options: MappingProxyType[str, Any]) -> dict:
    """Ollama options schema."""
    return {
        vol.Optional(
            CONF_PROMPT,
            description={"suggested_value": options.get(CONF_PROMPT, DEFAULT_PROMPT)},
        ): TemplateSelector(),
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
    }


def _get_title(model: str) -> str:
    """Get title for config entry."""
    if model.endswith(":latest"):
        model = model.split(":", maxsplit=1)[0]

    return model
