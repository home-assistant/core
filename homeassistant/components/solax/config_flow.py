"""Config flow for solax integration."""

import asyncio
from importlib.metadata import entry_points
import logging
from typing import Any, override

from solax import RealTimeAPI, discover
from solax.discovery import DiscoveryError
from solax.inverter import Inverter
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_MODEL, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers import config_validation as cv, selector

from .const import DOMAIN, SOLAX_INVERTER_ENTRY_POINT_GROUP

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_PASSWORD = ""


def _get_inverter_models() -> dict[str, type[Inverter]]:
    """Return the available inverter models keyed by their entry point name."""
    return {
        ep.name: ep.load()
        for ep in entry_points(group=SOLAX_INVERTER_ENTRY_POINT_GROUP)
    }


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_MODEL): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=sorted(_get_inverter_models()),
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


async def validate_api(data: dict[str, Any]) -> str:
    """Validate the credentials."""

    kwargs: dict[str, Any] = {"return_when": asyncio.FIRST_COMPLETED}
    if model := data.get(CONF_MODEL):
        kwargs["inverters"] = [_get_inverter_models()[model]]

    inverter = await discover(
        data[CONF_IP_ADDRESS], data[CONF_PORT], data[CONF_PASSWORD], **kwargs
    )
    response = await RealTimeAPI(inverter).get_data()
    return response.serial_number


class SolaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solax."""

    @override
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
        except ConnectionError, DiscoveryError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(serial_number)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=serial_number, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
