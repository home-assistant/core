"""Adds config flow for Petcare integration."""
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

# from .petcare import Petcare

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


async def validate_input(
    hass: core.HomeAssistant, user_input: dict[str, Any]
) -> str | None:
    """Validate the user input allows us to connect."""

    _LOGGER.info(f"validate_input(..) called with {user_input = }")

    try:
        surepy = Surepy(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            auth_token=None,
            api_timeout=SURE_API_TIMEOUT,
            session=async_get_clientsession(hass),
        )

        return await surepy.sac.get_token()

    except SurePetcareAuthenticationError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        raise SurePetcareAuthenticationError from error

    except SurePetcareError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: %s", error)
        raise SurePetcareError from error


class SurePetcareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore
    """Sure Petcare config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_import(
        self, import_info: dict[str, Any]
    ) -> data_entry_flow.FlowResult:
        """Set up entry from configuration.yaml file."""

        _LOGGER.info(f"async_step_import(..) called with {import_info = }")

        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """User step. Specify items in the order they are to be displayed in the UI."""

        errors: dict[str, Any] = {}

        _LOGGER.info(f"async_step_user(..) called with {user_input = }")

        if user_input:

            try:
                if token := await validate_input(self.hass, user_input):

                    uniq_username = user_input[CONF_USERNAME].casefold()
                    await self.async_set_unique_id(
                        uniq_username, raise_on_progress=False
                    )

                    return self.async_create_entry(
                        title="Sure Petcare",
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_TOKEN: token,
                        },
                    )
            except SurePetcareAuthenticationError:
                _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
                errors["invalid_auth"] = "invalid_auth"
                # return self.async_abort(reason="invalid_auth")

            except SurePetcareError as error:
                _LOGGER.error("Unable to connect to surepetcare.io: %s", error)
                errors["unknown"] = error
                # return self.async_abort(reason="unknown")

        _LOGGER.info(
            f"no user_input, calling async_show_form(..) with {DATA_SCHEMA = }"
        )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

        # return self.async_abort(reason="authentication_failed")
