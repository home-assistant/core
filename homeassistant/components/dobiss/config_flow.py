"""Config flow for dobiss integration."""

import logging
from typing import Any

from awesomeversion import AwesomeVersion
import dobissapi
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, __version__ as HAVERSION
from homeassistant.core import callback

from .const import CONF_SECRET, CONF_SECURE, DOMAIN

_LOGGER = logging.getLogger(__name__)

HA_VERSION = AwesomeVersion(HAVERSION)


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    dobiss = dobissapi.DobissAPI(data[CONF_SECRET], data[CONF_HOST], data[CONF_SECURE])

    try:
        if not await dobiss.auth_check():
            raise InvalidAuth
    except (ConnectionError, TimeoutError) as err:
        raise CannotConnect from err

    return {"title": f"NXT server {data[CONF_HOST]}"}


class DobissOptionsFlowHandler(OptionsFlow):
    """Handle a option flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        if HA_VERSION < "2024.12":
            self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema({})
        return self.async_show_form(step_id="init", data_schema=data_schema)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dobiss."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host_input = user_input[CONF_HOST].strip().lower()

            await self.async_set_unique_id(host_input)
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors[CONF_HOST] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_SECRET] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        else:
            user_input = {}

        secure: bool = user_input.get(CONF_SECURE, False)
        fields = {
            vol.Required(CONF_SECRET, default=user_input.get(CONF_SECRET)): str,
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
            vol.Optional(CONF_SECURE, default=secure): bool,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> DobissOptionsFlowHandler:
        """Get the options flow for AlarmDecoder."""
        return DobissOptionsFlowHandler(config_entry)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
