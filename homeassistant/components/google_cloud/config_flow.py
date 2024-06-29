"""Config flow for the Gogole Cloud integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from pathlib import Path
from typing import Any

from google.cloud import texttospeech
import voluptuous as vol

from homeassistant.components.tts import CONF_LANG
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_KEY_FILE,
    CONF_STT_MODEL,
    DEFAULT_LANG,
    DEFAULT_STT_MODEL,
    DOMAIN,
    SUPPORTED_STT_MODELS,
)
from .helpers import async_tts_voices, tts_options_schema

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_KEY_FILE): str,
    }
)


class GoogleCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Cloud integration."""

    VERSION = 1

    _name: str | None = None

    def __init__(self) -> None:
        """Initialize a new GoogleCloudConfigFlow."""
        self.reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}
        if user_input is not None:
            if Path(self.hass.config.path(user_input[CONF_KEY_FILE])).is_file():
                if self.reauth_entry:
                    return self.async_update_reload_and_abort(
                        self.reauth_entry,
                        data=user_input,
                    )
                return self.async_create_entry(
                    title="Google Cloud",
                    data=user_input,
                )
            errors["base"] = "file_not_found"
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is not None:
            return await self.async_step_user()
        assert self.reauth_entry
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                CONF_NAME: self.reauth_entry.title,
                CONF_KEY_FILE: self.reauth_entry.data.get(CONF_KEY_FILE, ""),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GoogleCloudOptionsFlowHandler:
        """Create the options flow."""
        return GoogleCloudOptionsFlowHandler(config_entry)


class GoogleCloudOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Google Cloud options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        key_file = self.hass.config.path(self.config_entry.data[CONF_KEY_FILE])
        client: texttospeech.TextToSpeechAsyncClient = (
            texttospeech.TextToSpeechAsyncClient.from_service_account_json(key_file)
        )
        voices = await async_tts_voices(client)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LANG,
                        description={"suggested_value": self.options.get(CONF_LANG)},
                        default=DEFAULT_LANG,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN, options=list(voices)
                        )
                    ),
                    **tts_options_schema(self.options, voices).schema,
                    vol.Optional(
                        CONF_STT_MODEL,
                        description={
                            "suggested_value": self.options.get(CONF_STT_MODEL)
                        },
                        default=DEFAULT_STT_MODEL,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=SUPPORTED_STT_MODELS,
                        )
                    ),
                }
            ),
        )
