"""Config flow for zeversolar integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import zeversolar

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    },
)


class ZeverSolarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zeversolar."""

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

        client = zeversolar.ZeverSolarClient(host=user_input[CONF_HOST])
        try:
            data = await self.hass.async_add_executor_job(client.get_data)
        except zeversolar.ZeverSolarHTTPNotFound:
            errors["base"] = "invalid_host"
        except zeversolar.ZeverSolarHTTPError:
            errors["base"] = "cannot_connect"
        except zeversolar.ZeverSolarTimeout:
            errors["base"] = "timeout_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(data.serial_number)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Zeversolar", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
