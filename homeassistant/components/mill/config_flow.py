"""Adds config flow for Mill integration."""

from typing import Any

from mill import Mill
from mill_local import Mill as MillLocal
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLOUD, CONNECTION_TYPE, DOMAIN, LOCAL


class MillConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mill integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = vol.Schema(
            {
                vol.Required(CONNECTION_TYPE, default=CLOUD): vol.In(
                    (
                        CLOUD,
                        LOCAL,
                    )
                )
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
            )

        if user_input[CONNECTION_TYPE] == LOCAL:
            return await self.async_step_local()
        return await self.async_step_cloud()

    async def async_step_local(self, user_input=None):
        """Handle the local step."""
        data_schema = vol.Schema({vol.Required(CONF_IP_ADDRESS): str})
        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=data_schema,
            )

        mill_data_connection = MillLocal(
            user_input[CONF_IP_ADDRESS],
            websession=async_get_clientsession(self.hass),
        )

        await self.async_set_unique_id(mill_data_connection.device_ip)
        self._abort_if_unique_id_configured()

        if not await mill_data_connection.connect():
            return self.async_show_form(
                step_id="local",
                data_schema=data_schema,
                errors={"base": "cannot_connect"},
            )

        return self.async_create_entry(
            title=user_input[CONF_IP_ADDRESS],
            data={
                CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                CONNECTION_TYPE: LOCAL,
            },
        )

    async def async_step_cloud(self, user_input=None):
        """Handle the cloud step."""
        data_schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )
        if user_input is None:
            return self.async_show_form(
                step_id="cloud",
                data_schema=data_schema,
                errors={},
            )

        username = user_input[CONF_USERNAME].replace(" ", "")
        password = user_input[CONF_PASSWORD].replace(" ", "")

        mill_data_connection = Mill(
            username,
            password,
            websession=async_get_clientsession(self.hass),
        )

        errors = {}

        if not await mill_data_connection.connect():
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="cloud",
                data_schema=data_schema,
                errors=errors,
            )

        unique_id = username

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONNECTION_TYPE: CLOUD,
            },
        )
