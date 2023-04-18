"""Config flow for Android IP Webcam integration."""
from __future__ import annotations

from typing import Any

from pydroid_ipcam import PyDroidIPCam
from pydroid_ipcam.exceptions import PyDroidIPCamException, Unauthorized
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Inclusive(CONF_USERNAME, "authentication"): str,
        vol.Inclusive(CONF_PASSWORD, "authentication"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""

    websession = async_get_clientsession(hass)
    cam = PyDroidIPCam(
        websession,
        data[CONF_HOST],
        data[CONF_PORT],
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        ssl=False,
    )
    errors = {}
    try:
        await cam.update()
    except Unauthorized:
        errors[CONF_USERNAME] = "invalid_auth"
        errors[CONF_PASSWORD] = "invalid_auth"
    except PyDroidIPCamException:
        errors["base"] = "cannot_connect"

    return errors


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Android IP Webcam."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )
        if not (errors := await validate_input(self.hass, user_input)):
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
