"""Config flow for Sense integration."""

from collections.abc import Mapping
from functools import partial
import logging
from typing import TYPE_CHECKING, Any

from sense_energy import (
    ASyncSenseable,
    SenseAuthenticationException,
    SenseMFARequiredException,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_PASSWORD, CONF_TIMEOUT
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


class SenseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sense."""

    VERSION = 1

    def __init__(self) -> None:
        """Init Config ."""
        self._gateway: ASyncSenseable | None = None
        self._auth_data: dict[str, Any] = {}

    async def validate_input(self, data: Mapping[str, Any]) -> None:
        """Validate the user input allows us to connect.

        Data has the keys from DATA_SCHEMA with values provided by the user.
        """
        self._auth_data.update(dict(data))
        timeout = self._auth_data[CONF_TIMEOUT]
        client_session = async_get_clientsession(self.hass)

        # Creating the AsyncSenseable object loads
        # ssl certificates which does blocking IO
        self._gateway = await self.hass.async_add_executor_job(
            partial(
                ASyncSenseable,
                api_timeout=timeout,
                wss_timeout=timeout,
                client_session=client_session,
            )
        )
        if TYPE_CHECKING:
            assert self._gateway
        self._gateway.rate_limit = ACTIVE_UPDATE_RATE
        await self._gateway.authenticate(
            self._auth_data[CONF_EMAIL], self._auth_data[CONF_PASSWORD]
        )

    async def create_entry_from_data(self):
        """Create the entry from the config data."""
        self._auth_data["access_token"] = self._gateway.sense_access_token
        self._auth_data["user_id"] = self._gateway.sense_user_id
        self._auth_data["device_id"] = self._gateway.device_id
        self._auth_data["refresh_token"] = self._gateway.refresh_token
        self._auth_data["monitor_id"] = self._gateway.sense_monitor_id
        existing_entry = await self.async_set_unique_id(self._auth_data[CONF_EMAIL])
        if not existing_entry:
            return self.async_create_entry(
                title=self._auth_data[CONF_EMAIL], data=self._auth_data
            )

        return self.async_update_reload_and_abort(existing_entry, data=self._auth_data)

    async def validate_input_and_create_entry(
        self, user_input: Mapping[str, Any], errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Validate the input and create the entry from the data."""
        try:
            await self.validate_input(user_input)
        except SenseMFARequiredException:
            return await self.async_step_validation()
        except SENSE_CONNECT_EXCEPTIONS:
            errors["base"] = "cannot_connect"
        except SenseAuthenticationException:
            errors["base"] = "invalid_auth"
        except Exception:
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
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.create_entry_from_data()

        return self.async_show_form(
            step_id="validation",
            data_schema=vol.Schema({vol.Required(CONF_CODE): vol.All(str, vol.Strip)}),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if result := await self.validate_input_and_create_entry(user_input, errors):
                return result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._auth_data = dict(entry_data)
        return await self.async_step_reauth_validate(entry_data)

    async def async_step_reauth_validate(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth and validation."""
        errors: dict[str, str] = {}
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
