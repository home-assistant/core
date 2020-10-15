"""Config flow to configure Amcrest devices."""

import logging

from amcrest import AmcrestError, LoginError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_USERNAME,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .amcrest_checker import AmcrestChecker
from .const import (
    AUTHENTICATION_LIST,
    CONF_BINARY_SENSOR_AUDIO_DETECTED,
    CONF_BINARY_SENSOR_AUDIO_DETECTED_POLLED,
    CONF_BINARY_SENSOR_MOTION_DETECTED,
    CONF_BINARY_SENSOR_MOTION_DETECTED_POLLED,
    CONF_BINARY_SENSOR_ONLINE,
    CONF_CONTROL_LIGHT,
    CONF_EVENTS,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RESOLUTION,
    CONF_SENSOR_PTZ_PRESET,
    CONF_SENSOR_SDCARD,
    CONF_STREAM_SOURCE,
    DEFAULT_AUTHENTICATION,
    DEFAULT_CONTROL_LIGHT,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RESOLUTION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STREAM_SOURCE,
    DEVICES,
    DOMAIN,
    RESOLUTION_LIST,
    STREAM_SOURCE_LIST,
)

_LOGGER = logging.getLogger(__name__)


class AmcrestFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Amcrest config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return AmcrestOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the Amcrest config flow."""
        self.device_config = {}
        self.discovery_schema = {}
        self.import_schema = {}

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        _LOGGER.debug("start import AMCREST: %s", import_config)
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle a Amcrest config flow start.

        Manage device specific parameters.
        """
        errors = {}

        if user_input is not None:
            try:
                device = AmcrestChecker(
                    self.hass,
                    user_input[CONF_NAME],
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )

                serial_number = device.serial_number.rstrip("\r\n")

                await self.async_set_unique_id(serial_number)

                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    }
                )

                self.device_config = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }

                return await self._create_entry()

            except LoginError:
                errors["base"] = "faulty_credentials"

            except AmcrestError:
                errors["base"] = "device_unavailable"

        data = self.discovery_schema or {
            vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        }

        return self.async_show_form(
            step_id="user",
            description_placeholders=self.device_config,
            data_schema=vol.Schema(data),
            errors=errors,
        )

    async def _create_entry(self):
        """Create entry for device."""

        return self.async_create_entry(
            title=self.device_config[CONF_NAME], data=self.device_config
        )


class AmcrestOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Amcrest device options."""

    def __init__(self, config_entry):
        """Initialize Amcrest device options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.device = None

    async def async_step_init(self, user_input=None):
        """Manage the Amcrest device options."""
        self.device = self.hass.data[DOMAIN][DEVICES][self.config_entry.data[CONF_NAME]]
        return await self.async_step_configure_stream()

    async def async_step_configure_stream(self, user_input=None):
        """Manage the Amcrest device options."""
        if user_input is not None:
            self.options.update(user_input)
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="configure_stream",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_STREAM_SOURCE,
                        default=self.config_entry.options.get(
                            CONF_STREAM_SOURCE, DEFAULT_STREAM_SOURCE
                        ),
                    ): vol.In(STREAM_SOURCE_LIST),
                    vol.Optional(
                        CONF_FFMPEG_ARGUMENTS,
                        default=self.config_entry.options.get(
                            CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
                        ),
                    ): str,
                    vol.Optional(
                        CONF_RESOLUTION,
                        default=self.config_entry.options.get(
                            CONF_RESOLUTION, DEFAULT_RESOLUTION
                        ),
                    ): vol.All(vol.In(RESOLUTION_LIST)),
                    vol.Optional(
                        CONF_AUTHENTICATION,
                        default=self.config_entry.options.get(
                            CONF_AUTHENTICATION, DEFAULT_AUTHENTICATION
                        ),
                    ): vol.All(vol.In(AUTHENTICATION_LIST)),
                    vol.Optional(
                        CONF_CONTROL_LIGHT,
                        default=self.config_entry.options.get(
                            CONF_CONTROL_LIGHT, DEFAULT_CONTROL_LIGHT
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): int,
                    vol.Optional(
                        CONF_BINARY_SENSORS,
                        default=self.config_entry.options.get(CONF_BINARY_SENSORS, []),
                    ): cv.multi_select(
                        {
                            CONF_BINARY_SENSOR_AUDIO_DETECTED: CONF_BINARY_SENSOR_AUDIO_DETECTED,
                            CONF_BINARY_SENSOR_AUDIO_DETECTED_POLLED: CONF_BINARY_SENSOR_AUDIO_DETECTED_POLLED,
                            CONF_BINARY_SENSOR_MOTION_DETECTED: CONF_BINARY_SENSOR_MOTION_DETECTED,
                            CONF_BINARY_SENSOR_MOTION_DETECTED_POLLED: CONF_BINARY_SENSOR_MOTION_DETECTED_POLLED,
                            CONF_BINARY_SENSOR_ONLINE: CONF_BINARY_SENSOR_ONLINE,
                        }
                    ),
                    vol.Optional(
                        CONF_SENSORS,
                        default=self.config_entry.options.get(CONF_SENSORS, []),
                    ): cv.multi_select(
                        {
                            CONF_SENSOR_PTZ_PRESET: CONF_SENSOR_PTZ_PRESET,
                            CONF_SENSOR_SDCARD: CONF_SENSOR_SDCARD,
                        }
                    ),
                    vol.Optional(
                        CONF_EVENTS,
                        default=self.config_entry.options.get(CONF_EVENTS, str),
                    ): str,
                }
            ),
        )
