"""Config flow for simplepush integration."""

from __future__ import annotations

from typing import Any

from simplepush import UnknownError, send
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD

from .const import ATTR_ENCRYPTED, CONF_DEVICE_KEY, CONF_SALT, DEFAULT_NAME, DOMAIN


def validate_input(entry: dict[str, str]) -> dict[str, str] | None:
    """Validate user input."""
    try:
        if CONF_PASSWORD in entry:
            send(
                key=entry[CONF_DEVICE_KEY],
                password=entry[CONF_PASSWORD],
                salt=entry[CONF_SALT],
                title="HA test",
                message="Message delivered successfully",
            )
        else:
            send(
                key=entry[CONF_DEVICE_KEY],
                title="HA test",
                message="Message delivered successfully",
            )
    except UnknownError:
        return {"base": "cannot_connect"}

    return None


class SimplePushFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for simplepush."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE_KEY])
            self._abort_if_unique_id_configured()

            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                }
            )

            if not (
                errors := await self.hass.async_add_executor_job(
                    validate_input, user_input
                )
            ):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_KEY): str,
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Inclusive(CONF_PASSWORD, ATTR_ENCRYPTED): str,
                    vol.Inclusive(CONF_SALT, ATTR_ENCRYPTED): str,
                }
            ),
            errors=errors,
        )
