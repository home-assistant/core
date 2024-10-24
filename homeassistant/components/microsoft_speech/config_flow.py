"""Config flow for Microsoft Speech integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import azure.cognitiveservices.speech as speechsdk
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_NAME, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    LanguageSelector,
    LanguageSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN, SUPPORTED_LANGUAGES, SUPPORTED_REGIONS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_REGION): SelectSelector(
            SelectSelectorConfig(options=SUPPORTED_REGIONS)
        ),
        vol.Required(CONF_LANGUAGE, default="en-US"): LanguageSelector(
            LanguageSelectorConfig(languages=SUPPORTED_LANGUAGES)
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    _LOGGER.debug("Fetching available voices")
    speech_config = speechsdk.SpeechConfig(
        subscription=data[CONF_API_KEY],
        region=data[CONF_REGION],
        speech_recognition_language=data[CONF_LANGUAGE],
    )

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
    voices_future = await hass.async_add_executor_job(synthesizer.get_voices_async)
    voices_result = await hass.async_add_executor_job(voices_future.get)

    if voices_result.reason == speechsdk.ResultReason.VoicesListRetrieved:
        _LOGGER.debug("Fetched %d voices", len(voices_result.voices))
        _LOGGER.debug(
            "Available voices: %s",
            ", ".join(voice.name for voice in voices_result.voices),
        )
    elif voices_result.reason == speechsdk.ResultReason.Canceled:
        _LOGGER.error("Error fetching voices: %s", voices_result.error_details)
        if hasattr(voices_result, "error_details"):
            if "Authentication error" in voices_result.error_details:
                raise InvalidAuth("Authentication failed due to invalid credentials")
            if "HTTPAPI_OPEN_REQUEST_FAILED" in voices_result.error_details:
                raise CannotConnect("Authentication failed due to connection problem")
        raise Exception("Authentication failed")  # noqa: TRY002

    return {"title": data[CONF_NAME]}


class MicrosoftSpeechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Microsoft Speech."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.entry: ConfigEntry

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        self.entry = self._get_reconfigure_entry()
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfiguration")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry, title=info["title"], data=user_input
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA,
                suggested_values=self.entry.data | (user_input or {}),
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization of an existing entry."""
        self.entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization of an existing entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge existing entry data with new user_input
            new_data = self.entry.data.copy()
            new_data.update(user_input)
            try:
                info = await validate_input(self.hass, new_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauthorization")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry, title=info["title"], data=new_data
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
