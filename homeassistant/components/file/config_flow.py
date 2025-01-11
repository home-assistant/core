"""Config flow for file integration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_FILE_PATH,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    Platform,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    TemplateSelector,
    TemplateSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_TIMESTAMP, DOMAIN

BOOLEAN_SELECTOR = BooleanSelector(BooleanSelectorConfig())
TEMPLATE_SELECTOR = TemplateSelector(TemplateSelectorConfig())
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))

FILE_OPTIONS_SCHEMAS = {
    Platform.SENSOR.value: vol.Schema(
        {
            vol.Optional(CONF_VALUE_TEMPLATE): TEMPLATE_SELECTOR,
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): TEXT_SELECTOR,
        }
    ),
    Platform.NOTIFY.value: vol.Schema(
        {
            vol.Optional(CONF_TIMESTAMP, default=False): BOOLEAN_SELECTOR,
        }
    ),
}

FILE_FLOW_SCHEMAS = {
    Platform.SENSOR.value: vol.Schema(
        {
            vol.Required(CONF_FILE_PATH): TEXT_SELECTOR,
        }
    ).extend(FILE_OPTIONS_SCHEMAS[Platform.SENSOR.value].schema),
    Platform.NOTIFY.value: vol.Schema(
        {
            vol.Required(CONF_FILE_PATH): TEXT_SELECTOR,
        }
    ).extend(FILE_OPTIONS_SCHEMAS[Platform.NOTIFY.value].schema),
}


class FileConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a file config flow."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> FileOptionsFlowHandler:
        """Get the options flow for this handler."""
        return FileOptionsFlowHandler()

    async def validate_file_path(self, file_path: str) -> bool:
        """Ensure the file path is valid."""
        return await self.hass.async_add_executor_job(
            self.hass.config.is_allowed_path, file_path
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["notify", "sensor"],
        )

    async def _async_handle_step(
        self, platform: str, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle file config flow step."""
        errors: dict[str, str] = {}
        if user_input:
            user_input[CONF_PLATFORM] = platform
            self._async_abort_entries_match(user_input)
            if not await self.validate_file_path(user_input[CONF_FILE_PATH]):
                errors[CONF_FILE_PATH] = "not_allowed"
            else:
                title = f"{platform.capitalize()} [{user_input[CONF_FILE_PATH]}]"
                data = deepcopy(user_input)
                options = {}
                for key, value in user_input.items():
                    if key not in (CONF_FILE_PATH, CONF_PLATFORM, CONF_NAME):
                        data.pop(key)
                        options[key] = value
                return self.async_create_entry(data=data, title=title, options=options)

        return self.async_show_form(
            step_id=platform, data_schema=FILE_FLOW_SCHEMAS[platform], errors=errors
        )

    async def async_step_notify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle file notifier config flow."""
        return await self._async_handle_step(Platform.NOTIFY.value, user_input)

    async def async_step_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle file sensor config flow."""
        return await self._async_handle_step(Platform.SENSOR.value, user_input)


class FileOptionsFlowHandler(OptionsFlow):
    """Handle File options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage File options."""
        if user_input:
            return self.async_create_entry(data=user_input)

        platform = self.config_entry.data[CONF_PLATFORM]
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                FILE_OPTIONS_SCHEMAS[platform], self.config_entry.options or {}
            ),
        )
