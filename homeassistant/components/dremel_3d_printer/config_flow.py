"""Config flow for Dremel 3D Printer (3D20, 3D40, 3D45)."""
from __future__ import annotations

from typing import Any

from dremel3dpy import Dremel3DPrinter
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


def _schema_with_defaults(host: str = "") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): cv.string,
        },
    )


class Dremel3DPrinterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dremel 3D Printer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=_schema_with_defaults(),
            )

        try:
            api = await self.hass.async_add_executor_job(
                Dremel3DPrinter, user_input[CONF_HOST]
            )
        except (ConnectTimeout, HTTPError):
            errors = {"base": "cannot_connect"}
        except Exception:  # pylint: disable=broad-except
            errors = {"base": "unknown"}

        if errors:
            return self.async_show_form(
                step_id="user",
                errors=errors,
                data_schema=_schema_with_defaults(host=user_input[CONF_HOST]),
            )

        await self.async_set_unique_id(api.get_serial_number())
        self._abort_if_unique_id_configured()
        config_data: dict[str, str] = {CONF_HOST: user_input[CONF_HOST]}
        return self.async_create_entry(title=api.get_title(), data=config_data)
