"""Config flow for the guntamatic integration."""

from __future__ import annotations

import logging
from typing import Any

from guntamatic.heater import Heater
import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class GuntamaticConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for guntamatic."""

    VERSION = 1
    _discovered_host = None

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery."""
        await self.async_set_unique_id(discovery_info.macaddress)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        self._discovered_host = discovery_info.ip
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is None and self._discovered_host is not None:
            user_input = {CONF_HOST: self._discovered_host}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                heater = Heater(user_input[CONF_HOST])
                data = await self.hass.async_add_executor_job(heater.get_data)
            except requests.exceptions.ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not data:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title="Guntamatic Heater", data=user_input
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
