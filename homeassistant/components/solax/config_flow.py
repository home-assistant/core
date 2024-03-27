"""Config flow for solax integration."""

from __future__ import annotations

import logging
from typing import Any

from solax import discover
from solax.discovery import REGISTRY, DiscoveryError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import CONF_SOLAX_INVERTER, DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
DEFAULT_PASSWORD = ""
DEFAULT_INVERTER = ""

REGISTRY_HASH = {cls.__name__: cls for cls in REGISTRY}

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(
            CONF_SOLAX_INVERTER, default=DEFAULT_INVERTER
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(REGISTRY_HASH.keys()),
                mode=selector.SelectSelectorMode.DROPDOWN,
                multiple=True,
            )
        ),
    }
)


async def validate_api(data) -> str:
    """Validate the credentials."""

    _LOGGER.debug("CONF_SOLAX_INVERTER entry: %s", data[CONF_SOLAX_INVERTER])

    invset = set()
    for cls_name in data[CONF_SOLAX_INVERTER]:
        invset.add(REGISTRY_HASH[cls_name])
    inverter = await discover(
        data[CONF_IP_ADDRESS],
        data[CONF_PORT],
        data[CONF_PASSWORD],
        inverters=invset,
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
        except (ConnectionError, DiscoveryError):
            errors["base"] = "cannot_connect"
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
