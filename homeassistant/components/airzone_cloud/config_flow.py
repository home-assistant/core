"""Config flow for Airzone Cloud."""
from __future__ import annotations

from typing import Any

from aioairzone_cloud.cloudapi import AirzoneCloudApi
from aioairzone_cloud.common import ConnectionOptions
from aioairzone_cloud.const import AZD_ID, AZD_NAME, AZD_WEBSERVERS
from aioairzone_cloud.exceptions import AirzoneCloudError, LoginError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for an Airzone Cloud device."""

    airzone: AirzoneCloudApi

    async def async_step_inst_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the installation selection."""
        errors = {}
        options: dict[str, str] = {}

        inst_desc = None
        inst_id = None
        if user_input is not None:
            inst_id = user_input[CONF_ID]

        try:
            inst_list = await self.airzone.list_installations()
        except AirzoneCloudError:
            errors["base"] = "cannot_connect"
        else:
            for inst in inst_list:
                _data = inst.data()
                _id = _data[AZD_ID]
                options[_id] = f"{_data[AZD_NAME]} {_data[AZD_WEBSERVERS][0]} ({_id})"
                if _id is not None and _id == inst_id:
                    inst_desc = options[_id]

        if user_input is not None and inst_desc is not None:
            await self.async_set_unique_id(inst_id)
            self._abort_if_unique_id_configured()

            user_input[CONF_USERNAME] = self.airzone.options.username
            user_input[CONF_PASSWORD] = self.airzone.options.password

            return self.async_create_entry(title=inst_desc, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=k, label=v)
                                for k, v in options.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if CONF_ID in user_input:
                return await self.async_step_inst_pick(user_input)

            self.airzone = AirzoneCloudApi(
                aiohttp_client.async_get_clientsession(self.hass),
                ConnectionOptions(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                ),
            )

            try:
                await self.airzone.login()
            except (AirzoneCloudError, LoginError):
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_inst_pick()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
