"""Sure Petcare config flow."""
from __future__ import annotations

import logging
from typing import Any

from surepy import Surepy
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant import config_entries, core, data_entry_flow
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SURE_API_TIMEOUT

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def is_valid(hass: core.HomeAssistant, user_input: dict[str, Any]) -> str | None:
    """Check if we can log in with the supplied credentials."""

    try:
        surepy = Surepy(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            auth_token=None,
            api_timeout=SURE_API_TIMEOUT,
            session=async_get_clientsession(hass),
        )

        return await surepy.sac.get_token()

    except SurePetcareAuthenticationError:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        return None

    except SurePetcareError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: %s", error)
        return None


class SurePetcareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore
    """Implementation of the Sure Petcare config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_import(
        self, import_info: dict[str, Any]
    ) -> data_entry_flow.FlowResult:
        """Set up entry from configuration.yaml file."""
        return await self.async_step_user(import_info)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle a flow start."""

        errors: dict[str, Any] = {}

        if not user_input:
            data_schema = {
                vol.Required("username"): str,
                vol.Required("password"): str,
            }

            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(data_schema), errors=errors
            )

        if token := await is_valid(self.hass, user_input):

            uniq_username = user_input[CONF_USERNAME].casefold()
            await self.async_set_unique_id(uniq_username, raise_on_progress=False)

            return self.async_create_entry(
                title="Sure Petcare",
                data={
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_TOKEN: token,
                },
            )

        return self.async_abort(reason="authentication_failed")
