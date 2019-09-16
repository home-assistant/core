"""Config flow to configure ecobee."""
import voluptuous as vol
from copy import copy

from pyecobee import (
    Ecobee,
    ECOBEE_CONFIG_FILENAME,
    ECOBEE_API_KEY,
    ECOBEE_REFRESH_TOKEN,
)

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback, HomeAssistantError
from homeassistant.util.json import load_json

from .const import (
    CONF_HOLD_TEMP,
    CONF_REFRESH_TOKEN,
    DATA_ECOBEE_CONFIG,
    DOMAIN,
    _LOGGER,
)


class EcobeeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an ecobee config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return EcobeeOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the ecobee flow."""
        self._ecobee = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            """Config entry already exists, only one allowed."""
            return self.async_abort(reason="one_instance_only")

        errors = {}
        stored_api_key = self.hass.data[DATA_ECOBEE_CONFIG].get(CONF_API_KEY)

        if user_input is not None:
            """Use the user-supplied API key to attempt to obtain a PIN from ecobee."""
            self._ecobee = Ecobee(config={ECOBEE_API_KEY: user_input[CONF_API_KEY]})

            if await self.hass.async_add_executor_job(self._ecobee.request_pin):
                """We have a PIN; move to the next step of the flow."""
                return await self.async_step_authorize()
            errors["base"] = "pin_request_failed"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_API_KEY, default=stored_api_key): str}
            ),
            errors=errors,
        )

    async def async_step_authorize(self, user_input=None):
        """Present the user with the PIN so that the app can be authorized on ecobee.com."""
        errors = {}

        if user_input is not None:
            """Attempt to obtain tokens from ecobee and finish the flow."""
            if await self.hass.async_add_executor_job(self._ecobee.request_tokens):
                """Refresh token obtained; create the config entry."""
                config = {
                    CONF_API_KEY: self._ecobee.api_key,
                    CONF_REFRESH_TOKEN: self._ecobee.refresh_token,
                }
                return self.async_create_entry(title=DOMAIN, data=config)
            errors["base"] = "token_request_failed"

        return self.async_show_form(
            step_id="authorize",
            errors=errors,
            description_placeholders={"pin": self._ecobee.pin},
        )

    async def async_step_import(self, import_data):
        """
        Import ecobee config from configuration.yaml.

        Triggered by async_setup only if a config entry doesn't already exist.
        If ecobee.conf exists, we will attempt to validate the credentials
        and create an entry if valid. Otherwise, we will delegate to the user
        step so that the user can continue the config flow.
        """
        try:
            legacy_config = await self.hass.async_add_executor_job(
                load_json, self.hass.config.path(ECOBEE_CONFIG_FILENAME)
            )
            ecobee = Ecobee(
                config={
                    ECOBEE_API_KEY: legacy_config[ECOBEE_API_KEY],
                    ECOBEE_REFRESH_TOKEN: legacy_config[ECOBEE_REFRESH_TOKEN],
                }
            )
            if await self.hass.async_add_executor_job(ecobee.refresh_tokens):
                """Credentials found and validated; create the entry."""
                _LOGGER.debug(
                    "Valid ecobee configuration found for import, creating config entry"
                )
                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        CONF_API_KEY: ecobee.api_key,
                        CONF_REFRESH_TOKEN: ecobee.refresh_token,
                    },
                )
        except (HomeAssistantError, KeyError):
            _LOGGER.debug(
                "No valid ecobee.conf configuration found for import, delegating to user step"
            )

        return await self.async_step_user()


class EcobeeOptionsFlowHandler(config_entries.OptionsFlow):
    """Manage ecobee options."""

    def __init__(self, config_entry):
        """Initialize ecobee options flow."""
        self.config_entry = config_entry
        self.options = copy(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Handle an options flow start."""
        return await self.async_step_ecobee_options()

    async def async_step_ecobee_options(self, user_input=None):
        """Manage the ecobee options."""
        if user_input is not None:
            self.options[CONF_HOLD_TEMP] = user_input[CONF_HOLD_TEMP]
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="ecobee_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HOLD_TEMP,
                        default=self.config_entry.options[CONF_HOLD_TEMP],
                    ): bool
                }
            ),
        )
