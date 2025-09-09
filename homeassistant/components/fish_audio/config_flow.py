"""Config flow for the Fish Audio integration."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

from fish_audio_sdk import Session
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import SelectOptionDict

from . import FishAudioConfigEntry
from .const import (
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_LANGUAGE,
    CONF_SELF_ONLY,
    CONF_SORT_BY,
    CONF_VOICE_ID,
    DOMAIN,
)
from .schemas import API_KEY_SCHEMA, get_filter_schema, get_model_selection_schema

_LOGGER = logging.getLogger(__name__)


class FishAudioConfigFlowManager:
    """Manage the configuration flow for Fish Audio."""

    def __init__(self, hass: HomeAssistant, session: Session) -> None:
        """Initialize."""
        self.hass = hass
        self.session = session

    async def async_get_models(
        self, self_only: bool, language: str | None, sort_by: str
    ) -> list[SelectOptionDict]:
        """Get the available models."""
        try:
            func = partial(
                self.session.list_models,
                self_only=self_only,
                language=language,
                sort_by=sort_by,
            )
            models_response = await self.hass.async_add_executor_job(func)
            models = models_response.items
        except Exception:
            _LOGGER.exception("Failed to fetch Fish Audio models")
            return []

        return [
            SelectOptionDict(value=model.id, label=model.title)
            for model in sorted(models, key=lambda m: m.title)
        ]

    def schema(
        self,
        options: dict[str, Any],
        model_options: list[SelectOptionDict],
    ) -> vol.Schema:
        """Return the schema for the configuration flow."""
        return get_model_selection_schema(options, model_options)

    async def show_filter_form(
        self,
        handler: FishAudioConfigFlow | OptionsFlow,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the filter form."""
        if isinstance(handler, FishAudioConfigFlow):
            data = handler.config_data
        else:
            assert isinstance(handler, OptionsFlowHandler)
            data = handler.options

        return handler.async_show_form(
            step_id="filter" if isinstance(handler, FishAudioConfigFlow) else "init",
            data_schema=get_filter_schema(data),
            errors=errors or {},
        )

    async def show_model_form(
        self,
        handler: FishAudioConfigFlow | OptionsFlow,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the model selection form."""
        if isinstance(handler, FishAudioConfigFlow):
            data = handler.config_data
        else:
            assert isinstance(handler, OptionsFlowHandler)
            data = handler.options

        models = await self.async_get_models(
            self_only=data.get(CONF_SELF_ONLY, False),
            language=data.get(CONF_LANGUAGE),
            sort_by=data.get(CONF_SORT_BY, "score"),
        )

        form_errors = errors or {}
        if not models:
            form_errors["base"] = "no_models_found"
            return await self.show_filter_form(handler, errors=form_errors)

        return handler.async_show_form(
            step_id="model",
            data_schema=self.schema(data, models),
            errors=form_errors,
        )


async def validate_api_key(hass: HomeAssistant, api_key: str) -> Session:
    """Validate the user input allows us to connect."""

    session = await hass.async_add_executor_job(Session, api_key)

    try:
        await hass.async_add_executor_job(session.get_api_credit)
    except Exception as exc:
        raise CannotConnect from exc

    return session


class FishAudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fish Audio."""

    VERSION = 1
    config_data: dict[str, Any] = {}
    manager: FishAudioConfigFlowManager

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: FishAudioConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                session = await validate_api_key(self.hass, user_input[CONF_API_KEY])
                self.manager = FishAudioConfigFlowManager(self.hass, session)
                self.config_data = user_input
                return await self.async_step_filter()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=API_KEY_SCHEMA,
            errors=errors,
        )

    async def async_step_filter(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Handle the filter selection step."""
        if user_input is not None:
            self.config_data.update(user_input)
            return await self.manager.show_model_form(self)

        return await self.manager.show_filter_form(self)

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the model selection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (voice_id := user_input.get(CONF_VOICE_ID)) and (
                backend := user_input.get(CONF_BACKEND)
            ):
                credit_info = await self.hass.async_add_executor_job(
                    self.manager.session.get_api_credit
                )
                await self.async_set_unique_id(
                    f"{credit_info.user_id}-{voice_id}-{backend}"
                )
                self._abort_if_unique_id_configured()

                self.config_data.update(user_input)
                data = {CONF_API_KEY: self.config_data[CONF_API_KEY]}
                options = {
                    key: self.config_data[key]
                    for key in self.config_data
                    if key not in (CONF_API_KEY, "name")
                }
                return self.async_create_entry(
                    title=self.config_data.get("name", "Fish Audio"),
                    data=data,
                    options=options,
                )
            errors["base"] = "no_model_selected"

        return await self.manager.show_model_form(self, errors=errors)


class OptionsFlowHandler(OptionsFlow):
    """Handle an options flow for Fish Audio."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.options = dict(config_entry.options)
        self.manager: FishAudioConfigFlowManager | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the filter selection step."""
        if self.manager is None:
            try:
                session = await validate_api_key(
                    self.hass, self.config_entry.data[CONF_API_KEY]
                )
                self.manager = FishAudioConfigFlowManager(self.hass, session)
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            self.options.update(user_input)
            return await self.manager.show_model_form(self)

        return await self.manager.show_filter_form(self)

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the model selection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_VOICE_ID):
                self.options.update(user_input)
                return self.async_create_entry(title="", data=self.options)
            errors["base"] = "no_model_selected"

        if self.manager is None:
            # This should not happen, but as a fallback.
            return self.async_abort(reason="unknown_error")

        return await self.manager.show_model_form(self, errors=errors)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
