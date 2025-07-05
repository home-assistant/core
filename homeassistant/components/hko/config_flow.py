"""Config flow for Hong Kong Observatory integration."""

from __future__ import annotations

from asyncio import timeout
import logging
from typing import Any

from hko import HKO, LOCATIONS, HKOError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LOCATION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import API_RHRREAD, DEFAULT_LOCATION, DOMAIN, KEY_LOCATION

_LOGGER = logging.getLogger(__name__)


def get_loc_name(item):
    """Return an array of supported locations."""
    return item[KEY_LOCATION]


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCATION, default=DEFAULT_LOCATION): SelectSelector(
            SelectSelectorConfig(options=list(map(get_loc_name, LOCATIONS)), sort=True)
        )
    }
)


class HKOConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hong Kong Observatory."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            websession = async_get_clientsession(self.hass)
            hko = HKO(websession)
            async with timeout(60):
                await hko.weather(API_RHRREAD)

        except HKOError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(
                user_input[CONF_LOCATION], raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_LOCATION], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
