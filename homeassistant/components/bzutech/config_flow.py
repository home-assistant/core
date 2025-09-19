"""Config flow for BZUTech integration."""

from __future__ import annotations

import logging
from typing import Any

from bzutech import BzuTech
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_CHIPID, CONF_ENDPOINT, CONF_SENSORPORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_LOGIN_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def get_api(data: dict[str, Any]) -> BzuTech:
    """Validate the user input allows us to connect."""

    return BzuTech(data[CONF_EMAIL], data[CONF_PASSWORD])


def get_ports(api: BzuTech, chipid: str) -> list[str]:
    """Get ports with the endpoints connected to each port."""
    return [f"Port {i} {api.get_endpoint_on(chipid, i)}" for i in range(1, 5)]


class BzuTechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BZUTech."""

    VERSION = 1
    api: BzuTech
    email = ""
    password = ""
    selecteddevice = 0
    selectedport = 0

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.api = get_api(user_input)
            if not await self.api.start():
                return self.async_abort(reason="Invalid Authentication")
            self.email = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]
            return await self.async_step_deviceselect(user_input=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_LOGIN_SCHEMA,
            errors=errors,
            last_step=False,
        )

    async def async_step_deviceselect(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the selection of the device from a list ."""
        if self.selecteddevice != 0 and user_input is not None:
            self.selecteddevice = user_input[CONF_CHIPID]
            return await self.async_step_portselect(user_input=user_input)
        self.selecteddevice = 1
        return self.async_show_form(
            step_id="deviceselect",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHIPID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=key, label=key)
                                for key in self.api.get_device_names()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_portselect(self, user_input) -> ConfigFlowResult:
        """Set up the device port selection."""
        if self.selectedport != 0:
            user_input = {
                CONF_ENDPOINT: user_input[CONF_SENSORPORT].split(" ")[2],
                CONF_SENSORPORT: user_input[CONF_SENSORPORT][5],
                CONF_PASSWORD: self.password,
                CONF_EMAIL: self.email,
                CONF_CHIPID: self.selecteddevice,
            }
            identifier = f"BZUGW-{self.selecteddevice}-{user_input[CONF_SENSORPORT]}"
            await self.async_set_unique_id(identifier)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=identifier,
                data=user_input,
            )

        self.selectedport = 1
        return self.async_show_form(
            step_id="portselect",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SENSORPORT): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=k, label=k)
                                for k in get_ports(self.api, user_input[CONF_CHIPID])
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )
