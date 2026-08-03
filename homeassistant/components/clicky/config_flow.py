"""Config flow for the Clicky Web Analytics integration."""

import logging
from typing import Any, override

from pyclicky import AuthenticationError, ClickyAPIError, ClickyClient, ConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN, METRICS

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SITE_ID): str,
        vol.Required(CONF_SITEKEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    client = ClickyClient(
        site_id=data[CONF_SITE_ID],
        sitekey=data[CONF_SITEKEY],
        session=session,
    )

    # Validate the API connection (and auth details) by making one API call
    try:
        await client.query(METRICS["visitorsOnline"])
    except AuthenticationError as error:
        raise InvalidAuth from error
    except ConnectionError as error:
        raise CannotConnect from error
    except ClickyAPIError as error:
        raise ConfigEntryAuthFailed(f"API failed for {data[CONF_SITE_ID]}") from error

    return {"title": data[CONF_SITE_ID]}


class ClickyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Clicky Web Analytics."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize a new ClickyConfigFlow."""
        self._data: dict[str, Any] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (website name and API credentials)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data.update(user_input)

            self._async_abort_entries_match({CONF_SITE_ID: self._data[CONF_SITE_ID]})
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
