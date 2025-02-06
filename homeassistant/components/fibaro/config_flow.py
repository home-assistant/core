"""Config flow for Fibaro integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from slugify import slugify
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import FibaroAuthFailed, FibaroConnectFailed, init_controller
from .const import CONF_IMPORT_PLUGINS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_IMPORT_PLUGINS, default=False): bool,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    controller = await hass.async_add_executor_job(init_controller, data)

    _LOGGER.debug(
        "Successfully connected to fibaro home center %s with name %s",
        controller.hub_serial,
        controller.hub_name,
    )
    return {
        "serial_number": slugify(controller.hub_serial),
        "name": controller.hub_name,
    }


def _normalize_url(url: str) -> str:
    """Try to fix errors in the entered url.

    We know that the url should be in the format http://<HOST>/api/
    """
    if url.endswith("/api"):
        return f"{url}/"
    if not url.endswith("/api/"):
        return f"{url}api/" if url.endswith("/") else f"{url}/api/"
    return url


class FibaroConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fibaro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                user_input[CONF_URL] = _normalize_url(user_input[CONF_URL])
                info = await _validate_input(self.hass, user_input)
            except FibaroConnectFailed:
                errors["base"] = "cannot_connect"
            except FibaroAuthFailed:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(info["serial_number"])
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title=info["name"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by reauthentication."""
        errors = {}

        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            new_data = reauth_entry.data | user_input
            try:
                await _validate_input(self.hass, new_data)
            except FibaroConnectFailed:
                errors["base"] = "cannot_connect"
            except FibaroAuthFailed:
                errors["base"] = "invalid_auth"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                CONF_NAME: reauth_entry.title,
            },
        )
