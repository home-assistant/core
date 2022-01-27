"""Config flow for laundrify integration."""
from __future__ import annotations

import logging

from laundrify_aio import LaundrifyAPI
from laundrify_aio.errors import ApiConnectionError, InvalidFormat, UnknownAuthCode
from voluptuous import All, Optional, Range, Required, Schema

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CODE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = Schema({Required(CONF_CODE): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for laundrify."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="init", data_schema=CONFIG_SCHEMA)

        errors = {}

        try:
            access_token = await LaundrifyAPI.exchange_auth_code(user_input[CONF_CODE])
        except InvalidFormat:
            errors[CONF_CODE] = "invalid_format"
        except UnknownAuthCode:
            errors[CONF_CODE] = "invalid_auth"
        except ApiConnectionError as err:
            _LOGGER.warning(str(err))
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            entry_data = {CONF_ACCESS_TOKEN: access_token}

            # The integration supports only a single config entry
            existing_entry = await self.async_set_unique_id(DOMAIN)
            if existing_entry:
                _LOGGER.info(
                    "%s entry already exists, going to update and reload it", DOMAIN
                )
                self.hass.config_entries.async_update_entry(
                    existing_entry, data=entry_data
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="single_instance_allowed")

            # Create a new entry if it doesn't exist
            return self.async_create_entry(
                title=DOMAIN,
                data=entry_data,
            )

        return self.async_show_form(
            step_id="init", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=Schema({}),
            )
        return await self.async_step_init()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for laundrify."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=Schema(
                {
                    Optional(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): All(int, Range(min=10)),
                }
            ),
        )
