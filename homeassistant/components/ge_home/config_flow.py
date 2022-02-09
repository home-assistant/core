"""Config flow for GE Home integration."""

import logging
from typing import Dict, Optional

import aiohttp
import asyncio
import async_timeout

from gehomesdk import GeAuthFailedError, GeNotAuthenticatedError, GeGeneralServerError, async_get_oauth2_token
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN  # pylint:disable=unused-import
from .exceptions import HaAuthError, HaCannotConnect, HaAlreadyConfigured

_LOGGER = logging.getLogger(__name__)

GEHOME_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)

async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    session = hass.helpers.aiohttp_client.async_get_clientsession(hass)

    # noinspection PyBroadException
    try:
        with async_timeout.timeout(10):
            _ = await async_get_oauth2_token(session, data[CONF_USERNAME], data[CONF_PASSWORD])
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise HaCannotConnect('Connection failure')
    except (GeAuthFailedError, GeNotAuthenticatedError):
        raise HaAuthError('Authentication failure')
    except GeGeneralServerError:
        raise HaCannotConnect('Cannot connect (server error)')
    except Exception as exc:
        _LOGGER.exception("Unknown connection failure", exc_info=exc)
        raise HaCannotConnect('Unknown connection failure')

    # Return info that you want to store in the config entry.
    return {"title": f"{data[CONF_USERNAME]:s}"}

class GeHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GE Home."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def _async_validate_input(self, user_input):
        """Validate form input."""
        errors = {}
        info = None

        if user_input is not None:
            # noinspection PyBroadException
            try:
                info = await validate_input(self.hass, user_input)
            except HaCannotConnect:
                errors["base"] = "cannot_connect"
            except HaAuthError:
                errors["base"] = "invalid_auth"      
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        return info, errors

    def _ensure_not_configured(self, username: str):
        """Ensure that we haven't configured this account"""
        existing_accounts = {
            entry.data[CONF_USERNAME] for entry in self._async_current_entries()
        }
        _LOGGER.debug(f"Existing accounts: {existing_accounts}")
        if username in existing_accounts:
            raise HaAlreadyConfigured  

    async def async_step_user(self, user_input: Optional[Dict] = None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                self._ensure_not_configured(user_input[CONF_USERNAME])
                info, errors = await self._async_validate_input(user_input)
                if info:
                    return self.async_create_entry(title=info["title"], data=user_input)
            except HaAlreadyConfigured:
                return self.async_abort(reason="already_configured_account")


        return self.async_show_form(
            step_id="user", data_schema=GEHOME_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input: Optional[dict] = None):
        """Handle re-auth if login is invalid."""
        errors = {}

        if user_input is not None:
            _, errors = await self._async_validate_input(user_input)

            if not errors:
                for entry in self._async_current_entries():
                    if entry.unique_id == self.unique_id:
                        self.hass.config_entries.async_update_entry(
                            entry, data=user_input
                        )
                        await self.hass.config_entries.async_reload(entry.entry_id)
                        return self.async_abort(reason="reauth_successful")

            if errors["base"] != "invalid_auth":
                return self.async_abort(reason=errors["base"])

        return self.async_show_form(
            step_id="reauth", data_schema=GEHOME_SCHEMA, errors=errors,
        )
