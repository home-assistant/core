"""Config flow to configure Amcrest integration."""
from __future__ import annotations

import logging
from typing import Any

from amcrest import AmcrestError, LoginError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENSORS,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from . import AmcrestChecker
from .binary_sensor import (
    AUDIO_DETECTED_KEY,
    AUDIO_DETECTED_POLLED_KEY,
    BINARY_SENSORS,
    CROSSLINE_DETECTED_KEY,
    CROSSLINE_DETECTED_POLLED_KEY,
    MOTION_DETECTED_KEY,
    MOTION_DETECTED_POLLED_KEY,
)
from .const import (
    CONF_CONTROL_LIGHT,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RESOLUTION,
    CONF_STREAM_SOURCE,
    DEFAULT_CONTROL_LIGHT,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RESOLUTION,
    DEFAULT_STREAM_SOURCE,
    DOMAIN,
    RESOLUTION_LIST,
    STREAM_SOURCE_LIST,
)
from .sensor import SENSORS

_LOGGER = logging.getLogger(__name__)

SETUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

EXCLUSIVE_BINARY_SENSORS = [
    {AUDIO_DETECTED_KEY, AUDIO_DETECTED_POLLED_KEY},
    {MOTION_DETECTED_KEY, MOTION_DETECTED_POLLED_KEY},
    {CROSSLINE_DETECTED_KEY, CROSSLINE_DETECTED_POLLED_KEY},
]


class AmcrestConfigFlow(ConfigFlow, domain=DOMAIN):
    """Amcrest config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AmcrestOptionsFlow:
        """Get the options flow for this handler."""
        return AmcrestOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}
        if user_input:
            try:
                camera = AmcrestChecker(
                    self.hass,
                    user_input[CONF_NAME],
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )

                serial_number = await camera.async_serial_number
            except LoginError:
                errors["base"] = "invalid_auth"
            except AmcrestError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unhandled exception in user step")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )

                data = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }

                # Setup options from user input to handle configuration.yaml import.
                options = {
                    CONF_FFMPEG_ARGUMENTS: user_input.get(
                        CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
                    ),
                    CONF_RESOLUTION: user_input.get(
                        CONF_RESOLUTION, DEFAULT_RESOLUTION
                    ),
                    CONF_STREAM_SOURCE: user_input.get(
                        CONF_STREAM_SOURCE, DEFAULT_STREAM_SOURCE
                    ),
                    CONF_BINARY_SENSORS: user_input.get(CONF_BINARY_SENSORS, []),
                    CONF_SENSORS: user_input.get(CONF_SENSORS, []),
                    CONF_CONTROL_LIGHT: user_input.get(
                        CONF_CONTROL_LIGHT, DEFAULT_CONTROL_LIGHT
                    ),
                }

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=data, options=options
                )

        return self.async_show_form(
            step_id="user", data_schema=SETUP_SCHEMA, errors=errors or {}
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import Amecrest config from configuration.yaml."""
        return await self.async_step_user(import_data)


class AmcrestOptionsFlow(OptionsFlow):
    """Amcrest options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize an Amcrest options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Conifgure the camera."""
        errors: dict[str, str] = {}

        if user_input is None:
            user_input = dict(**self._config_entry.options)
        else:
            binary_sensors = set(user_input.get(CONF_BINARY_SENSORS, []))
            for exclusive_binary_sensors in EXCLUSIVE_BINARY_SENSORS:
                if len(binary_sensors & exclusive_binary_sensors) > 1:
                    errors["base"] = "exclusive_binary_sensors"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FFMPEG_ARGUMENTS,
                        default=user_input.get(
                            CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
                        ),
                    ): str,
                    vol.Optional(
                        CONF_RESOLUTION,
                        default=user_input.get(CONF_RESOLUTION, DEFAULT_RESOLUTION),
                    ): vol.In(RESOLUTION_LIST),
                    vol.Optional(
                        CONF_STREAM_SOURCE,
                        default=user_input.get(
                            CONF_STREAM_SOURCE, DEFAULT_STREAM_SOURCE
                        ),
                    ): vol.In(STREAM_SOURCE_LIST),
                    vol.Optional(
                        CONF_BINARY_SENSORS,
                        default=user_input.get(CONF_BINARY_SENSORS, []),
                    ): cv.multi_select(
                        {sensor.key: sensor.name for sensor in BINARY_SENSORS}
                    ),
                    vol.Optional(
                        CONF_SENSORS,
                        default=user_input.get(CONF_SENSORS, []),
                    ): cv.multi_select({sensor.key: sensor.name for sensor in SENSORS}),
                    vol.Optional(
                        CONF_CONTROL_LIGHT,
                        default=user_input.get(
                            CONF_CONTROL_LIGHT, DEFAULT_CONTROL_LIGHT
                        ),
                    ): bool,
                }
            ),
        )
