"""Config flow for Gogogate2."""
import logging
from typing import Optional

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .common import async_can_connect, get_api
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def row_kwargs(default: Optional[str]) -> dict:
    """Provide optional kwargs."""
    return {"default": default} if default is not None else {}


def data_schema(data: dict = None) -> vol.Schema:
    """Return options schema."""
    data = data or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, **row_kwargs(data.get(CONF_NAME))): str,
            vol.Required(CONF_IP_ADDRESS, **row_kwargs(data.get(CONF_IP_ADDRESS))): str,
            vol.Required(CONF_USERNAME, **row_kwargs(data.get(CONF_USERNAME))): str,
            vol.Required(CONF_PASSWORD, **row_kwargs(data.get(CONF_PASSWORD))): str,
        }
    )


async def async_handle_data_updated(
    flow_handler: data_entry_flow.FlowHandler, user_input: dict
) -> dict:
    """Handle data being updated."""
    api = get_api(user_input)

    if not await async_can_connect(flow_handler.hass, api):
        return flow_handler.async_abort(
            reason="cannot_connect",
            description_placeholders={CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]},
        )

    return flow_handler.async_create_entry(title=user_input[CONF_NAME], data=user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Init object."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return await async_handle_data_updated(self, user_input)

        return self.async_show_form(
            step_id="init", data_schema=data_schema(self._config_entry.data),
        )


@config_entries.HANDLERS.register(DOMAIN)
class Gogogate2FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Gogogate2 config flow."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlowHandler:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_import(self, config_data: dict = None):
        """Handle importing of configuration."""
        return await self.async_step_finish(config_data)

    async def async_step_user(self, user_input: dict = None):
        """Handle user initiated flow."""
        if user_input is not None:
            return await self.async_step_finish(user_input)

        return self.async_show_form(step_id="user", data_schema=data_schema(),)

    async def async_step_finish(self, user_input: dict):
        """Validate and create config entry."""
        return await async_handle_data_updated(self, user_input)
