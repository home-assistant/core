"""Config flow for Local access to the zeversolar invertor integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from zeversolarlocal import api

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, ZEVER_HOST, ZEVER_INVERTER_ID, ZEVER_URL

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(ZEVER_HOST): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    url = api.default_url(data[ZEVER_HOST])

    # If parsing of data is wrong this will raise ZeverSolarError.
    # If invertor is not reachable (which could be normal as it runs on
    # solar energy) it will raise ZeverSolarTimeout.
    inverter_id = await api.inverter_id(url)

    return {
        "title": "Zeversolar invertor.",
        ZEVER_URL: url,
        ZEVER_INVERTER_ID: inverter_id,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Local access to the zeversolar invertor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step when user initializes a integration."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except api.ZeverError:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(info[ZEVER_INVERTER_ID])
            return self.async_create_entry(title=info["title"], data=info)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
