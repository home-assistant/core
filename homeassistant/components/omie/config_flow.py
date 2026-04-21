"""Config flow for OMIE - Spain and Portugal electricity prices integration."""

from typing import Any, Final

from aiohttp import ClientError
import pyomie.main as pyomie

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .util import CET

DEFAULT_NAME: Final = "OMIE"


class OMIEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """OMIE config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the first and only step."""
        if user_input is not None:
            errors: dict[str, str] = {}
            session = async_get_clientsession(self.hass)
            cet_today = dt_util.now().astimezone(CET).date()
            try:
                await pyomie.spot_price(session, cet_today)
            except ClientError, TimeoutError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=DEFAULT_NAME, data={})
            return self.async_show_form(step_id="user", errors=errors)

        return self.async_show_form(step_id="user")
