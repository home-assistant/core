import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (DOMAIN, CONF_HOME_ASSISTANT_ACCESS_TOKEN, CONF_LOCAL_ACCESS_TOKEN,
                    NAME, CONF_UNLOCK_PULLS_LATCH, CONF_USE_CLOUD)

_LOGGER = logging.getLogger(__name__)

class TedeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    
    def __init__(self):
        self._errors: dict = {}
        self._reload: dict = False
        self._previous_step_data: dict = {}
        self._config: dict = {}

    async def async_step_user(self, user_input: dict[str, Any]=None) -> FlowResult:
        errors: dict = {}
        
        if user_input is not None:
            if (user_input.get(CONF_HOST) is None and user_input.get(CONF_LOCAL_ACCESS_TOKEN) is not None) \
                or (user_input.get(CONF_HOST) is not None and user_input.get(CONF_LOCAL_ACCESS_TOKEN) is None):
                errors["base"] = "invalid_local_config"
            elif not user_input.get(CONF_USE_CLOUD, False) and user_input.get(CONF_LOCAL_ACCESS_TOKEN) is None and user_input.get(CONF_ACCESS_TOKEN) is None:
                errors["base"] = "invalid_config"
            if not errors:

                if user_input.get(CONF_USE_CLOUD, False):
                    self._previous_step_data = user_input
                    return await self.async_step_configure_cloud()
                
                return self.async_create_entry(
                        title=NAME, 
                        data=user_input
                    )
        
        return self.async_show_form(
            step_id="user", 
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST): str,
                    vol.Optional(CONF_LOCAL_ACCESS_TOKEN): str,
                    vol.Optional(CONF_HOME_ASSISTANT_ACCESS_TOKEN): str,
                    vol.Optional(CONF_USE_CLOUD, False): bool
                }
            ),
            errors=errors
        )
    
    async def async_step_configure_cloud(self, user_input: dict[str, Any]=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=NAME, 
                data=user_input | self._previous_step_data
            )
        else:
            return self.async_show_form(
                step_id="configure_cloud", 
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ACCESS_TOKEN): str
                    }
                ),
                errors=errors
            )
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)
    
    
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._config = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any]=None) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_ACCESS_TOKEN, default=self._config.get(CONF_ACCESS_TOKEN, "")): str,
                        vol.Optional(CONF_LOCAL_ACCESS_TOKEN, default=self._config.get(CONF_LOCAL_ACCESS_TOKEN, "")): str,
                    }
                ),
            )
        entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self.hass.config_entries.async_update_entry(
            entry, 
            data=self._config | user_input
        )   
        await self.hass.config_entries.async_reload(self.context["entry_id"])
        return self.async_abort(reason="reauth_successful")
    
    
class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry


    async def async_step_init(
        self, user_input: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Manage the options for the custom component."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not errors:
                # write entry to config and not options dict, pass empty options out
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=user_input, options=self.config_entry.options
                )   
                return self.async_create_entry(
                    title="",
                    data=user_input
                )

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_ACCESS_TOKEN, default=self.config_entry.data.get(CONF_ACCESS_TOKEN, "")): str,
                vol.Optional(CONF_UNLOCK_PULLS_LATCH, default=self.config_entry.options.get(CONF_UNLOCK_PULLS_LATCH, False)): bool,
                vol.Optional(CONF_HOST, default=self.config_entry.data.get(CONF_HOST, "")): str,
                vol.Optional(CONF_LOCAL_ACCESS_TOKEN, default=self.config_entry.data.get(CONF_LOCAL_ACCESS_TOKEN, "")): str,
                vol.Optional(CONF_HOME_ASSISTANT_ACCESS_TOKEN, default=self.config_entry.data.get(CONF_HOME_ASSISTANT_ACCESS_TOKEN, "")): str,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )