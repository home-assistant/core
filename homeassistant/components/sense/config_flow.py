"""Config flow for Sense integration."""
from collections.abc import Mapping
import logging
from typing import Any

from sense_energy import (
    ASyncSenseable,
    SenseAuthenticationException,
    SenseMFARequiredException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_PASSWORD, CONF_TIMEOUT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACTIVE_UPDATE_RATE, DEFAULT_TIMEOUT, DOMAIN, SENSE_CONNECT_EXCEPTIONS

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sense."""

    VERSION = 1

    def __init__(self):
        """Init Config ."""
        self._gateway = None
        self._auth_data = {}
        super().__init__()

    async def validate_input(self, data):
        """Validate the user input allows us to connect.

        Data has the keys from DATA_SCHEMA with values provided by the user.
        """
        self._auth_data.update(dict(data))
        timeout = self._auth_data[CONF_TIMEOUT]
        client_session = async_get_clientsession(self.hass)

        self._gateway = ASyncSenseable(
            api_timeout=timeout, wss_timeout=timeout, client_session=client_session
        )
        self._gateway.rate_limit = ACTIVE_UPDATE_RATE
        await self._gateway.authenticate(
            self._auth_data[CONF_EMAIL], self._auth_data[CONF_PASSWORD]
        )

    async def create_entry_from_data(self):
        """Create the entry from the config data."""
        self._auth_data["access_token"] = self._gateway.sense_access_token
        self._auth_data["user_id"] = self._gateway.sense_user_id
        self._auth_data["monitor_id"] = self._gateway.sense_monitor_id
        existing_entry = await self.async_set_unique_id(self._auth_data[CONF_EMAIL])
        if not existing_entry:
            return self.async_create_entry(
                title=self._auth_data[CONF_EMAIL], data=self._auth_data
            )

        self.hass.config_entries.async_update_entry(
            existing_entry, data=self._auth_data
        )
        await self.hass.config_entries.async_reload(existing_entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    async def validate_input_and_create_entry(self, user_input, errors):
        """Validate the input and create the entry from the data."""
        try:
            await self.validate_input(user_input)
        except SenseMFARequiredException:
            return await self.async_step_validation()
        except SENSE_CONNECT_EXCEPTIONS:
            errors["base"] = "cannot_connect"
        except SenseAuthenticationException:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return await self.create_entry_from_data()
        return None

    async def async_step_validation(self, user_input=None):
        """Handle validation (2fa) step."""
        errors = {}
        if user_input:
            try:
                await self._gateway.validate_mfa(user_input[CONF_CODE])
            except SENSE_CONNECT_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            except SenseAuthenticationException:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.create_entry_from_data()

        return self.async_show_form(
            step_id="validation",
            data_schema=vol.Schema({vol.Required(CONF_CODE): vol.All(str, vol.Strip)}),
            errors=errors,
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if result := await self.validate_input_and_create_entry(user_input, errors):
                return result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._auth_data = dict(entry_data)
        return await self.async_step_reauth_validate(entry_data)

    async def async_step_reauth_validate(self, user_input=None):
        """Handle reauth and validation."""
        errors = {}
        if user_input is not None:
            if result := await self.validate_input_and_create_entry(user_input, errors):
                return result

        return self.async_show_form(
            step_id="reauth_validate",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={
                CONF_EMAIL: self._auth_data[CONF_EMAIL],
            },
        )
