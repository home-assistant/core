"""Config flow for pushbullet integration."""

from typing import Any, override

import probatio
from pushbullet import InvalidKeyError, PushBullet, PushbulletError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.helpers import selector

from .const import DOMAIN

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): selector.TextSelector(),
    }
)


class PushBulletConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pushbullet integration."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                pushbullet = await self.hass.async_add_executor_job(
                    PushBullet, user_input[CONF_API_KEY]
                )
            except InvalidKeyError:
                errors[CONF_API_KEY] = "invalid_api_key"
            except PushbulletError:
                errors["base"] = "cannot_connect"

            if not errors:
                user_info = pushbullet.user_info
                await self.async_set_unique_id(user_info["iden"])
                self._abort_if_unique_id_configured()
                name = user_info.get("name") or user_info["email"]
                return self.async_create_entry(
                    title=name,
                    data={CONF_NAME: name, **user_input},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )
