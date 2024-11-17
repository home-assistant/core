"""Config flow for the Playstation Network integration."""

import logging
from typing import Any

from psnawp_api.core.psnawp_exceptions import PSNAWPAuthenticationError
from psnawp_api.models import client
from psnawp_api.psnawp import PSNAWP
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required("npsso"): str})


class PlaystationNetworkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Playstation Network."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            psn = PSNAWP(user_input.get("npsso", ""))
            user: client.Client = await self.hass.async_add_executor_job(psn.me)
        except PSNAWPAuthenticationError as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="not_ready",
            ) from e
        except AbortFlow:
            errors = {"base": "This account is already configured"}
        else:
            await self.async_set_unique_id(user.account_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user.online_id,
                data={
                    "title": "Playstation Network",
                    "npsso": user_input.get("npsso"),
                    "username": user.online_id,
                    "account": user.account_id,
                    "data": user_input,
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
