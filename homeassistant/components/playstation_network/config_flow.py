"""Config flow for the PlayStation Network integration."""

import logging
from typing import Any

from psnawp_api.core.psnawp_exceptions import PSNAWPAuthenticationError, PSNAWPNotFound
from psnawp_api.models.user import User
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_NPSSO, DOMAIN
from .helpers import PlaystationNetwork

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
            npsso = PlaystationNetwork.parse_npsso_token(user_input[CONF_NPSSO])
            psn = PlaystationNetwork(npsso)
            try:
                user: User = await self.hass.async_add_executor_job(psn.get_user)
            except PSNAWPAuthenticationError:
                errors["base"] = "invalid_auth"
            except PSNAWPNotFound:
                errors["base"] = "invalid_account"
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
