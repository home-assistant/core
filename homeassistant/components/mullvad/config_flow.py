"""Config flow for Mullvad VPN integration."""

import logging
from typing import Any

from mullvad_api import MullvadAPI, MullvadAPIError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MullvadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mullvad VPN."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(MullvadAPI)
            except MullvadAPIError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Mullvad VPN", data=user_input)

        return self.async_show_form(step_id="user", errors=errors)
