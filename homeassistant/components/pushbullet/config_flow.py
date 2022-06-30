"""Config flow for pushbullet integration."""
from __future__ import annotations

from typing import Any

from pushbullet import InvalidKeyError, PushBullet
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class PushBulletConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pushbullet integration."""

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle import from config."""
        import_config[CONF_NAME] = import_config.get(CONF_NAME, DEFAULT_NAME)
        return await self.async_step_user(import_config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_API_KEY])
            self._abort_if_unique_id_configured()

            self._async_abort_entries_match({CONF_NAME: user_input[CONF_NAME]})

            try:
                await self.hass.async_add_executor_job(
                    PushBullet, user_input[CONF_API_KEY]
                )
            except InvalidKeyError:
                errors[CONF_API_KEY] = "invalid_api_key"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )
