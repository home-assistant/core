"""Config flow for solax integration."""

from __future__ import annotations

import asyncio
from importlib.metadata import entry_points
import logging
from typing import Any

from solax import discover
from solax.discovery import DiscoveryError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import CONF_SOLAX_INVERTER, DOMAIN, SOLAX_ENTRY_POINT_GROUP

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_PASSWORD = ""
DEFAULT_INVERTER = ""

INVERTERS_ENTRY_POINTS = {
    ep.name: ep.load() for ep in entry_points(group=SOLAX_ENTRY_POINT_GROUP)
}

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_SOLAX_INVERTER): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(INVERTERS_ENTRY_POINTS.keys()),
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=False,
            )
        ),
    }
)


async def validate_api(data) -> str:
    """Validate the credentials."""

    _LOGGER.debug("CONF_SOLAX_INVERTER entry: %s", data.get(CONF_SOLAX_INVERTER))

    invset = set()
    if CONF_SOLAX_INVERTER in data:
        invset.add(INVERTERS_ENTRY_POINTS.get(data.get(CONF_SOLAX_INVERTER)))
    else:
        for ep in INVERTERS_ENTRY_POINTS.values():
            invset.add(ep)

    inverter = await discover(
        data[CONF_IP_ADDRESS],
        data[CONF_PORT],
        data[CONF_PASSWORD],
        inverters=invset,
        return_when=asyncio.FIRST_COMPLETED,
    )

    response = await inverter.get_data()
    _LOGGER.debug("Solax serial number %s", response.serial_number)
    return response.serial_number


class SolaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solax."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            serial_number = await validate_api(user_input)
        except ConnectionError:
            errors["base"] = "cannot_connect"
        except DiscoveryError:
            errors["base"] = "inverter discovery error"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=serial_number, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
