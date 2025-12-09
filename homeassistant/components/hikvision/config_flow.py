"""Config flow for Hikvision integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pyhik.hikvision import HikCamera
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HikvisionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            ssl = user_input[CONF_SSL]

            protocol = "https" if ssl else "http"
            url = f"{protocol}://{host}"

            try:
                camera = await self.hass.async_add_executor_job(
                    HikCamera, url, port, username, password
                )
                device_id = camera.get_id
                device_name = camera.get_name
            except Exception:
                _LOGGER.exception("Error connecting to Hikvision device")
                errors["base"] = "cannot_connect"
            else:
                if device_id is None:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=device_name or host,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                            CONF_SSL: ssl,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization request."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            host = reauth_entry.data[CONF_HOST]
            port = reauth_entry.data[CONF_PORT]
            ssl = reauth_entry.data[CONF_SSL]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            protocol = "https" if ssl else "http"
            url = f"{protocol}://{host}"

            try:
                camera = await self.hass.async_add_executor_job(
                    HikCamera, url, port, username, password
                )
                device_id = camera.get_id
            except Exception:
                _LOGGER.exception("Error connecting to Hikvision device")
                errors["base"] = "cannot_connect"
            else:
                if device_id is None:
                    errors["base"] = "cannot_connect"
                elif device_id != reauth_entry.unique_id:
                    errors["base"] = "wrong_device"
                else:
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data_updates={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                        },
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
