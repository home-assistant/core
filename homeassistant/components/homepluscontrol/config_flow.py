"""Config flow for Legrand Home+ Control."""
import logging
import re
import time
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.network import get_url

from .api import update_api_refresh_intervals
from .const import (
    CONF_MODULE_STATUS_UPDATE_INTERVAL,
    CONF_PLANT_TOPOLOGY_UPDATE_INTERVAL,
    CONF_PLANT_UPDATE_INTERVAL,
    CONF_REDIRECT_URI,
    CONF_SUBSCRIPTION_KEY,
    DEFAULT_UPDATE_INTERVALS,
    DOMAIN,
)
from .helpers import HomePlusControlOAuth2Implementation


class HomePlusControlFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Home+ Control OAuth2 authentication."""

    DOMAIN = DOMAIN

    # Pick the Cloud Poll class
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input=None):
        """Handle a flow start initiated by the user."""
        await self.async_set_unique_id(DOMAIN)

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        assert self.hass
        errors = {}

        if user_input is not None:
            # Validate user input
            valid = await self._is_valid(user_input, errors)
            if valid:
                user_input["implementation"] = DOMAIN
                self.async_register_implementation(
                    self.hass,
                    HomePlusControlOAuth2Implementation(self.hass, user_input),
                )
                return await super().async_step_user(user_input)

        DOMAIN_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Required(CONF_SUBSCRIPTION_KEY): cv.string,
                vol.Required(
                    CONF_REDIRECT_URI,
                    default=get_url(self.hass)
                    + config_entry_oauth2_flow.AUTH_CALLBACK_PATH,
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=DOMAIN_SCHEMA, errors=errors
        )

    async def async_step_creation(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create the config entry for the flow from the external authentication data.

        Overrides the base class method to handle general exceptions and to add additional config information for the entry.

        Args:.
            data (dict): Dictionary containing the additional configuration data to be stored.
        """
        try:
            token = await self.flow_impl.async_resolve_external_data(self.external_data)

            # Force int for non-compliant oauth2 providers
            token["expires_in"] = int(token["expires_in"])
        except ValueError as err:
            self.logger.warning("Error converting expires_in to int: %s", err)
            return self.async_abort(reason="oauth_error")
        except Exception as err:
            self.logger.warning("Error retrieving authentication token: %s", err)
            return self.async_abort(reason="oauth_error")

        token["expires_at"] = time.time() + token["expires_in"]
        self.logger.info("Successfully authenticated")

        config_data = {}
        config_data[CONF_CLIENT_ID] = self.flow_impl.client_id
        config_data[CONF_CLIENT_SECRET] = self.flow_impl.client_secret
        config_data[CONF_SUBSCRIPTION_KEY] = self.flow_impl.subscription_key
        config_data[CONF_REDIRECT_URI] = self.flow_impl.redirect_uri

        return self.async_create_entry(
            title=self.flow_impl.name,
            data={
                "auth_implementation": self.flow_impl.domain,
                "token": token,
                **config_data,
            },
        )

    async def _is_valid(self, user_input, errors):
        """Validate the user input."""
        # Subscription Key has to be a 32 alphanumeric string
        regex = "[0-9a-zA-Z]{32}"
        compiled = re.compile(regex)
        if not compiled.match(user_input[CONF_SUBSCRIPTION_KEY]):
            errors[CONF_SUBSCRIPTION_KEY] = "invalid_subscription_key"
            return False
        return True

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the Options Flow Handler for the Home+ Control component."""
        return HomePlusControlOptionsFlowHandler(config_entry)


class HomePlusControlOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler for the Home+ Control integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize the HomePlusControlOptionsFlowHandler object."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

        self.options.setdefault(
            CONF_PLANT_UPDATE_INTERVAL,
            DEFAULT_UPDATE_INTERVALS[CONF_PLANT_UPDATE_INTERVAL],
        )
        self.options.setdefault(
            CONF_PLANT_TOPOLOGY_UPDATE_INTERVAL,
            DEFAULT_UPDATE_INTERVALS[CONF_PLANT_TOPOLOGY_UPDATE_INTERVAL],
        )
        self.options.setdefault(
            CONF_MODULE_STATUS_UPDATE_INTERVAL,
            DEFAULT_UPDATE_INTERVALS[CONF_MODULE_STATUS_UPDATE_INTERVAL],
        )

    async def async_step_init(self, user_input=None):
        """Handle the integration options."""
        assert self.hass
        errors = {}
        if self.hass.data[DOMAIN].get("options_listener_remover") is None:
            self.hass.data[DOMAIN][
                "options_listener_remover"
            ] = self.config_entry.add_update_listener(update_api_refresh_intervals)

        if user_input is not None:
            # Validate user input
            valid = await self._is_valid(user_input, errors)
            if valid:
                return self.async_create_entry(title="Home+ Control", data=user_input)

        OPTIONS_SCHEMA = vol.Schema(
            {
                vol.Optional(
                    CONF_PLANT_UPDATE_INTERVAL,
                    default=self.options[CONF_PLANT_UPDATE_INTERVAL],
                ): cv.string,
                vol.Optional(
                    CONF_PLANT_TOPOLOGY_UPDATE_INTERVAL,
                    default=self.options[CONF_PLANT_TOPOLOGY_UPDATE_INTERVAL],
                ): cv.string,
                vol.Optional(
                    CONF_MODULE_STATUS_UPDATE_INTERVAL,
                    default=self.options[CONF_MODULE_STATUS_UPDATE_INTERVAL],
                ): cv.string,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=OPTIONS_SCHEMA, errors=errors
        )

    async def _is_valid(self, user_input, errors):
        """Validate the user input to the config options flow."""
        # Input expected to be in seconds
        valid = True
        regex = "[0-9]{1,5}"
        compiled = re.compile(regex)
        for input_key, input_value in user_input.items():
            if compiled.match(input_value):
                try:
                    int_input_value = int(input_value)
                    if int_input_value > 0 and int_input_value <= 86400:
                        continue
                except ValueError:
                    pass
            errors[input_key] = "invalid_update_interval"
            valid = False
        return valid
