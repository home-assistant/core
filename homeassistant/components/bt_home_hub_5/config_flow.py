"""Config flow for BT Home Hub 5 integration."""

import logging
from typing import Any, override

from bthomehub5_devicelist import get_devicelist
import probatio
import requests

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DEFAULT_HOST, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST, default=DEFAULT_HOST): str,
    }
)


async def _async_validate_host(hass: HomeAssistant, host: str) -> None:
    """Validate that we can connect to the host."""
    devicelist = await hass.async_add_executor_job(get_devicelist, host)
    if devicelist is None:
        raise requests.exceptions.ConnectionError("Device list is None")


class BTHomeHub5ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BT Home Hub 5."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]

            self._async_abort_entries_match({CONF_HOST: host})

            try:
                await _async_validate_host(self.hass, host)
            except requests.exceptions.RequestException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"BT Home Hub 5 ({host})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from legacy YAML."""
        host = import_data[CONF_HOST]

        self._async_abort_entries_match({CONF_HOST: host})

        try:
            await _async_validate_host(self.hass, host)
        except requests.exceptions.RequestException:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=f"BT Home Hub 5 ({host})",
            data=import_data,
        )
