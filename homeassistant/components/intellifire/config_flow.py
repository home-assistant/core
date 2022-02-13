"""Config flow for IntelliFire integration."""
from __future__ import annotations

from typing import Any

from aiohttp import ClientConnectionError
from aiohttp.client_reqrep import ConnectionKey
from intellifire4py import IntellifireAsync, IntellifireControlAsync
from intellifire4py.control import LoginException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SSL, default=True): bool,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


async def validate_host_input(hass: HomeAssistant, host: str) -> str:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api = IntellifireAsync(host)
    await api.poll()

    # Return the serial number which will be used to calculate a unique ID for the device/sensors
    return api.data.serial


async def validate_api_access(hass: HomeAssistant, user_input: dict[str, Any]):
    """Validate username/password against api."""
    ift_control = IntellifireControlAsync(
        fireplace_ip=user_input[CONF_HOST],
        use_http=(not user_input[CONF_SSL]),
        verify_ssl=user_input[CONF_VERIFY_SSL],
    )
    try:
        await ift_control.login(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
        )
        await ift_control.get_username()

    finally:
        await ift_control.close()


class IntellifireConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IntelliFire."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        errors = {}

        try:
            serial = await validate_host_input(self.hass, user_input[CONF_HOST])
            # If we don't throw an error everything is peachy!
            await validate_api_access(self.hass, user_input)
        except (ConnectionError, ClientConnectionError) as error:
            errors["base"] = "cannot_connect"
            if len(error.args) > 0:
                if isinstance(error.args[0], ConnectionKey):
                    arg0: ConnectionKey = error.args[0]
                    if arg0.host == "iftapi.net":
                        errors["base"] = "iftapi_connect"
        except LoginException:
            errors["base"] = "api_error"
        else:
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_SSL: user_input[CONF_SSL],
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                }
            )
            return self.async_create_entry(
                title="Fireplace",
                data={
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_SSL: user_input[CONF_SSL],
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                },
            )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
