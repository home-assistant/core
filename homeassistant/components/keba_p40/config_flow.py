"""Config flow for the KEBA P40 integration."""

from typing import Any

from keba_kecontact_p40 import (
    KebaP40AuthError,
    KebaP40Client,
    KebaP40ConnectionError,
    KebaP40Error,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DEFAULT_PORT, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


class KebaP40ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KEBA P40."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = KebaP40Client(
                user_input[CONF_HOST],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass, verify_ssl=False),
                port=user_input[CONF_PORT],
            )
            try:
                await client.login()
                wallboxes = await client.get_wallboxes()
            except KebaP40AuthError:
                errors["base"] = "invalid_auth"
            except KebaP40ConnectionError:
                errors["base"] = "cannot_connect"
            except KebaP40Error:
                errors["base"] = "unknown"
            else:
                if not wallboxes:
                    errors["base"] = "no_wallbox"
                else:
                    wallbox = wallboxes[0]
                    await self.async_set_unique_id(wallbox.serial_number)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=wallbox.alias or wallbox.model or "KEBA P40",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )
