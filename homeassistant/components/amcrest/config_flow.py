"""Config flow for Amcrest integration."""

import logging
from typing import Any

from amcrest import AmcrestError, LoginError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_USERNAME,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from . import (
    CONF_CONTROL_LIGHT,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RESOLUTION,
    CONF_STREAM_SOURCE,
    DEFAULT_ARGUMENTS,
    DEFAULT_PORT,
    DEFAULT_RESOLUTION,
    AmcrestChecker,
)
from .camera import STREAM_SOURCE_LIST
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ENTRY_TITLE_PREFIX = "Amcrest"


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
        serial_number = await api.async_serial_number
    except LoginError:
        return (None, "invalid_auth")
    except AmcrestError:
        return (None, "cannot_connect")
    except Exception:
        _LOGGER.exception("Unexpected exception during config flow")
        return (None, "unknown")
    else:
        if not serial_number:
            return (None, "no_serial_number")
        return (serial_number.strip(), None)


def _build_user_options() -> dict[str, Any]:
    """Return default options for UI-created config entries."""
    return {
        CONF_RESOLUTION: DEFAULT_RESOLUTION,
        CONF_STREAM_SOURCE: STREAM_SOURCE_LIST[0],
        CONF_FFMPEG_ARGUMENTS: DEFAULT_ARGUMENTS,
        CONF_CONTROL_LIGHT: True,
    }


def _build_import_options(import_data: dict[str, Any]) -> dict[str, Any]:
    """Return options mapped from a YAML camera configuration."""
    return {
        CONF_RESOLUTION: import_data.get(CONF_RESOLUTION, DEFAULT_RESOLUTION),
        CONF_STREAM_SOURCE: import_data.get(CONF_STREAM_SOURCE, STREAM_SOURCE_LIST[0]),
        CONF_FFMPEG_ARGUMENTS: import_data.get(
            CONF_FFMPEG_ARGUMENTS, DEFAULT_ARGUMENTS
        ),
        CONF_CONTROL_LIGHT: import_data.get(CONF_CONTROL_LIGHT, True),
        CONF_AUTHENTICATION: import_data.get(
            CONF_AUTHENTICATION, HTTP_BASIC_AUTHENTICATION
        ),
        CONF_BINARY_SENSORS: import_data.get(CONF_BINARY_SENSORS) or [],
        CONF_SENSORS: import_data.get(CONF_SENSORS) or [],
        CONF_SWITCHES: import_data.get(CONF_SWITCHES) or [],
    }


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

            serial_number, error = await _validate_connection(
                self.hass, host, port, username, password
            )

            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"{ENTRY_TITLE_PREFIX} {serial_number}",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                    options=_build_user_options(),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML."""
        self._async_abort_entries_match(
            {CONF_HOST: import_data[CONF_HOST], CONF_PORT: import_data[CONF_PORT]}
        )

        serial_number, error = await _validate_connection(
            self.hass,
            import_data[CONF_HOST],
            import_data[CONF_PORT],
            import_data[CONF_USERNAME],
            import_data[CONF_PASSWORD],
        )
        if error:
            return self.async_abort(reason=error)

        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=import_data[CONF_NAME],
            data={
                CONF_HOST: import_data[CONF_HOST],
                CONF_PORT: import_data[CONF_PORT],
                CONF_USERNAME: import_data[CONF_USERNAME],
                CONF_PASSWORD: import_data[CONF_PASSWORD],
            },
            options=_build_import_options(import_data),
        )
