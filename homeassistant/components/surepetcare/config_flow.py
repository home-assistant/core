"""Config flow for Sure Petcare integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import surepy
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SURE_API_TIMEOUT

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    surepy_client = surepy.Surepy(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        auth_token=None,
        api_timeout=SURE_API_TIMEOUT,
        session=async_get_clientsession(hass),
    )

    token = await surepy_client.sac.get_token()

    return {CONF_TOKEN: token}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sure Petcare."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._username: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_DATA_SCHEMA)

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except SurePetcareAuthenticationError:
            errors["base"] = "invalid_auth"
        except SurePetcareError:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            user_input[CONF_TOKEN] = info[CONF_TOKEN]
            return self.async_create_entry(
                title="Sure Petcare",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        if user_input is not None:
            user_input[CONF_USERNAME] = self._username
            try:
                await validate_input(self.hass, user_input)
            except SurePetcareAuthenticationError:
                errors["base"] = "invalid_auth"
            except SurePetcareError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                existing_entry = await self.async_set_unique_id(
                    user_input[CONF_USERNAME].lower()
                )
                if existing_entry:
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"username": self._username},
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
