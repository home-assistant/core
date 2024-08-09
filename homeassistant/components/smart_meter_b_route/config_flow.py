"""Config flow for Smart Meter B Route integration."""

import logging
from typing import Any

from momonga import Momonga, MomongaSkJoinFailure, MomongaSkScanFailure
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD

from .const import DOMAIN, ENTRY_TITLE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): str,
        vol.Required(CONF_ID): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def validate_input(device: str, id: str, password: str) -> None:
    """Validate the user input allows us to connect."""
    with Momonga(dev=device, rbid=id, pwd=password):
        pass


class BRouteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Meter B Route."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    validate_input,
                    user_input[CONF_DEVICE],
                    user_input[CONF_ID],
                    user_input[CONF_PASSWORD],
                )
            except MomongaSkScanFailure:
                errors["base"] = "cannot_connect"
            except MomongaSkJoinFailure:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    user_input[CONF_ID], raise_on_progress=False
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=ENTRY_TITLE, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
