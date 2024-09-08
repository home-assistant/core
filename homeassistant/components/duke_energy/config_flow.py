"""Config flow for Duke Energy integration."""

from __future__ import annotations

import logging
from typing import Any

from aiodukeenergy import DukeEnergy
from aiohttp import ClientError, ClientResponseError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class DukeEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Duke Energy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = DukeEnergy(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session
            )
            try:
                auth = await api.authenticate()
            except ClientResponseError as e:
                errors["base"] = (
                    "invalid_auth" if e.status == 404 else "could_not_connect"
                )
            except (ClientError, TimeoutError):
                errors["base"] = "could_not_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                email = auth["email"].lower()
                data = {CONF_EMAIL: email, **user_input}
                self._async_abort_entries_match(data)
                return self.async_create_entry(title=email, data=data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
