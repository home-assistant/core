"""Config flow for the QR Generator integration."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template

from .const import (
    CONF_ADVANCED,
    CONF_BACKGROUND_COLOR,
    CONF_BORDER,
    CONF_COLOR,
    CONF_ERROR_CORRECTION,
    CONF_SCALE,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_BORDER,
    DEFAULT_COLOR,
    DEFAULT_ERROR_CORRECTION,
    DEFAULT_SCALE,
    DOMAIN,
    ERROR_CORRECTION_LEVEL,
    HEX_COLOR_REGEX,
)


def get_schema(config: dict[str, Any] | None = None) -> vol.Schema:
    """Generate the schema."""
    if not config:
        config = {}

    default_name: str = config.get(CONF_NAME, "")
    default_value: str = config.get(CONF_VALUE_TEMPLATE, "")

    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=default_name): cv.string,
            vol.Required(CONF_VALUE_TEMPLATE, default=default_value): cv.string,
            vol.Optional(CONF_ADVANCED, default=False): cv.boolean,
        }
    )


def get_schema_advanced(config: dict[str, Any] | None = None) -> vol.Schema:
    """Generate the schema for the advanced settings."""
    if not config:
        config = {}

    default_color: str = config.get(CONF_COLOR, DEFAULT_COLOR)
    default_scale: int = config.get(CONF_SCALE, DEFAULT_SCALE)
    default_border: int = config.get(CONF_BORDER, DEFAULT_BORDER)
    default_error_correction: str = config.get(
        CONF_ERROR_CORRECTION, DEFAULT_ERROR_CORRECTION
    )
    default_background_color: str = config.get(
        CONF_BACKGROUND_COLOR, DEFAULT_BACKGROUND_COLOR
    )

    return vol.Schema(
        {
            vol.Required(CONF_COLOR, default=default_color): cv.string,
            vol.Required(
                CONF_BACKGROUND_COLOR, default=default_background_color
            ): cv.string,
            vol.Required(CONF_SCALE, default=default_scale): cv.positive_int,
            vol.Required(CONF_BORDER, default=default_border): cv.positive_int,
            vol.Required(
                CONF_ERROR_CORRECTION, default=default_error_correction
            ): vol.In(ERROR_CORRECTION_LEVEL),
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for QR Generator."""

    VERSION: int = 1

    override_config: dict[str, Any] = {}

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()

        self.config: dict[str, Any] = self.override_config

    async def async_step_user(
        self: ConfigFlow,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}

        if user_input is not None and not errors:
            try:
                template.Template(  # type: ignore[no-untyped-call]
                    user_input[CONF_VALUE_TEMPLATE], self.hass
                ).async_render()
            except TemplateError:
                errors["base"] = "invalid_template"
                return self.async_show_form(
                    step_id="user", data_schema=get_schema(), errors=errors
                )

            self.config = user_input

            if user_input[CONF_ADVANCED]:
                return await self.async_step_advanced()

            return self.async_create_entry(
                title=self.config[CONF_NAME], data=self.config
            )

        return self.async_show_form(
            step_id="user", data_schema=get_schema(), errors=errors
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step for advanced settings."""
        errors: dict[str, Any] = {}

        if user_input is not None and not errors:
            regex = re.compile(HEX_COLOR_REGEX)

            if regex.match(user_input[CONF_COLOR]) and regex.match(
                user_input[CONF_BACKGROUND_COLOR]
            ):
                self.config.update(user_input)

                return self.async_create_entry(
                    title=self.config[CONF_NAME], data=self.config
                )

            errors["base"] = "invalid_color"

        return self.async_show_form(
            step_id="advanced", data_schema=get_schema_advanced(), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for QR Generator."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.data = dict(self.config_entry.data)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        errors: dict[str, Any] = {}

        if user_input is not None and not errors:

            try:
                template.Template(  # type: ignore[no-untyped-call]
                    user_input[CONF_VALUE_TEMPLATE], self.hass
                ).async_render()
            except TemplateError:
                errors["base"] = "invalid_template"
                return self.async_show_form(
                    step_id="init", data_schema=get_schema(self.data), errors=errors
                )

            self.data.update(user_input)

            if user_input[CONF_ADVANCED]:
                return await self.async_step_advanced()

            return self.async_create_entry(title="", data=self.data)

        return self.async_show_form(
            step_id="init", data_schema=get_schema(self.data), errors=errors
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step for advanced settings."""
        errors: dict[str, Any] = {}

        if user_input is not None and not errors:
            regex = re.compile(HEX_COLOR_REGEX)

            if regex.match(user_input[CONF_COLOR]) and regex.match(
                user_input[CONF_BACKGROUND_COLOR]
            ):
                self.data.update(user_input)

                return self.async_create_entry(title="", data=self.data)

            errors["base"] = "invalid_color"

        return self.async_show_form(
            step_id="advanced",
            data_schema=get_schema_advanced(self.data),
            errors=errors,
        )
