"""Config flow for Dremel 3D Printer (3D20, 3D40, 3D45)."""

from __future__ import annotations

from json.decoder import JSONDecodeError
from typing import Any

from dremel3dpy import Dremel3DPrinter
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, LOGGER


def _schema_with_defaults(host: str = "") -> vol.Schema:
    return vol.Schema({vol.Required(CONF_HOST, default=host): cv.string})


class Dremel3DPrinterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dremel 3D Printer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=_schema_with_defaults(),
            )
        host = user_input[CONF_HOST]

        try:
            api = await self.hass.async_add_executor_job(Dremel3DPrinter, host)
        except (ConnectTimeout, HTTPError, JSONDecodeError):
            errors = {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("An unknown error has occurred")
            errors = {"base": "unknown"}

        if errors:
            return self.async_show_form(
                step_id="user",
                errors=errors,
                data_schema=_schema_with_defaults(host=host),
            )

        await self.async_set_unique_id(api.get_serial_number())
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=api.get_title(), data={CONF_HOST: host})
