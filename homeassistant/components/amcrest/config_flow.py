"""Config flow for Amcrest integration."""

from __future__ import annotations

import logging
from typing import Any

from amcrest import AmcrestError, LoginError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import AmcrestChecker
from .camera import STREAM_SOURCE_LIST
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_RESOLUTION = "resolution"
CONF_STREAM_SOURCE = "stream_source"
CONF_FFMPEG_ARGUMENTS = "ffmpeg_arguments"
CONF_CONTROL_LIGHT = "control_light"
DEFAULT_NAME = "Amcrest Camera"
DEFAULT_PORT = 80
DEFAULT_RESOLUTION = "high"
DEFAULT_ARGUMENTS = "-pred 1"


async def _validate_connection(
    hass: HomeAssistant,
    host: str,
    port: int,
    username: str,
    password: str,
) -> tuple[str | None, str | None]:
    """Validate the connection and return (serial_number, error)."""
    api = AmcrestChecker(hass, "config_flow", host, port, username, password)

    try:
        await api.async_current_time
        serial_number = (await api.async_serial_number or "").strip()
    except LoginError:
        return (None, "invalid_auth")
    except AmcrestError:
        return (None, "cannot_connect")
    except Exception:
        _LOGGER.exception("Unexpected exception during config flow")
        return (None, "unknown")
    else:
        return (serial_number or None, None)


class AmcrestFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amcrest."""

    VERSION = 1

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
            name = user_input.get(CONF_NAME, DEFAULT_NAME)

            serial_number, error = await _validate_connection(
                self.hass, host, port, username, password
            )

            if error:
                errors["base"] = error
            else:
                unique_id = serial_number or f"{host}:{port}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_NAME: name,
                    },
                    options={
                        CONF_RESOLUTION: DEFAULT_RESOLUTION,
                        CONF_STREAM_SOURCE: STREAM_SOURCE_LIST[0],
                        CONF_FFMPEG_ARGUMENTS: DEFAULT_ARGUMENTS,
                        CONF_CONTROL_LIGHT: True,
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
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )
