"""Config flow for the PlayStation Network integration."""

import json
import logging
from typing import Any

from psnawp_api.core.psnawp_exceptions import PSNAWPAuthenticationError, PSNAWPException
from psnawp_api.models.user import User
from psnawp_api.psn import PlaystationNetwork
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_NPSSO, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_NPSSO): str})


class PlaystationNetworkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Playstation Network."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                npsso = parse_npsso_token(user_input.get(CONF_NPSSO, ""))
                psn = PlaystationNetwork(npsso)
                user: User = await self.hass.async_add_executor_job(psn.get_user)
            except PSNAWPAuthenticationError:
                errors["base"] = "invalid_auth"
            except PSNAWPException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user.account_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user.online_id,
                    data={CONF_NPSSO: npsso},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "npsso_link": "https://ca.account.sony.com/api/v1/ssocookie",
                "psn_link": "https://playstation.com",
            },
        )


def parse_npsso_token(user_input: str = "") -> str:
    """Accept a string from the user that may contain either a valid npsso token or a json string with key "npsso" and value of the npsso token.

    This function either succeeds at extracting the npsso token from the provided input
    (meaning a valid npsso json string was provided) or it returns the original input.
    """
    try:
        npsso_input = json.loads(user_input)
        return npsso_input["npsso"]
    except Exception:  # noqa: BLE001
        return user_input
