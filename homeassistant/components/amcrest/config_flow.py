"""Config flow for Amcrest IP camera integration."""

from __future__ import annotations

import logging
from typing import Any

from amcrest import AmcrestError, ApiWrapper, LoginError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, selector

from .camera import STREAM_SOURCE_LIST
from .const import DOMAIN, RESOLUTION_LIST

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Amcrest Camera"
DEFAULT_PORT = 80
DEFAULT_RESOLUTION = "high"
DEFAULT_ARGUMENTS = "-pred 1"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class AmcrestConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Amcrest IP camera."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Check if we're in reconfigure mode
                if self.source == "reconfigure":
                    reconfigure_entry = self._get_reconfigure_entry()

                    # Check if unique ID has changed (different camera)
                    unique_id = None
                    try:
                        unique_id = await self.hass.async_add_executor_job(
                            _get_unique_id,
                            user_input[CONF_HOST],
                            user_input[CONF_PORT],
                            user_input[CONF_USERNAME],
                            user_input[CONF_PASSWORD],
                        )

                        # If we got a unique ID and it's different, ensure it's not already configured
                        if unique_id and unique_id != reconfigure_entry.unique_id:
                            await self.async_set_unique_id(unique_id)
                            self._abort_if_unique_id_mismatch(reason="wrong_device")

                    except (AmcrestError, AttributeError, KeyError, TypeError):
                        # If we can't get unique ID, continue anyway
                        pass

                    # Update the config entry with new data
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data_updates=user_input,
                        reason="reconfigure_successful",
                    )

                # Normal setup flow - check for unique ID to prevent duplicates
                unique_id = None
                try:
                    # Try to get a unique identifier from the camera
                    unique_id = await self.hass.async_add_executor_job(
                        _get_unique_id,
                        user_input[CONF_HOST],
                        user_input[CONF_PORT],
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                    )

                    if unique_id:
                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_configured()

                except (AmcrestError, AttributeError, KeyError, TypeError):
                    # If we can't get unique ID, continue anyway
                    pass

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        # Determine the schema to use
        if self.source == "reconfigure":
            # Pre-populate with existing values for reconfigure
            reconfigure_entry = self._get_reconfigure_entry()
            current_data = reconfigure_entry.data
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=current_data.get(CONF_HOST, "")
                    ): cv.string,
                    vol.Required(
                        CONF_USERNAME, default=current_data.get(CONF_USERNAME, "")
                    ): cv.string,
                    vol.Required(
                        CONF_PASSWORD, default=current_data.get(CONF_PASSWORD, "")
                    ): cv.string,
                    vol.Optional(
                        CONF_NAME, default=current_data.get(CONF_NAME, DEFAULT_NAME)
                    ): cv.string,
                    vol.Optional(
                        CONF_PORT, default=current_data.get(CONF_PORT, DEFAULT_PORT)
                    ): cv.port,
                }
            )
        else:
            # Use default schema for normal setup
            data_schema = STEP_USER_DATA_SCHEMA

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of existing camera."""
        # Simply redirect to the user step, which will handle reconfigure logic
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AmcrestOptionsFlowHandler:
        """Create the options flow."""
        return AmcrestOptionsFlowHandler(config_entry)


class AmcrestOptionsFlowHandler(OptionsFlow):
    """Handle Amcrest options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        pass
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_options()

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        # Get current options or set defaults
        options = self.config_entry.options

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_AUTHENTICATION,
                    default=options.get(CONF_AUTHENTICATION, HTTP_BASIC_AUTHENTICATION),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value="basic", label="Basic"),
                        ]
                    )
                ),
                vol.Optional(
                    "resolution",
                    default=options.get("resolution", DEFAULT_RESOLUTION),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=key, label=key.capitalize())
                            for key in RESOLUTION_LIST
                        ]
                    )
                ),
                vol.Optional(
                    "stream_source",
                    default=options.get("stream_source", STREAM_SOURCE_LIST[0]),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=source, label=source)
                            for source in STREAM_SOURCE_LIST
                        ]
                    )
                ),
                vol.Optional(
                    "ffmpeg_arguments",
                    default=options.get("ffmpeg_arguments", DEFAULT_ARGUMENTS),
                ): cv.string,
                vol.Optional(
                    "control_light",
                    default=options.get("control_light", True),
                ): cv.boolean,
                vol.Optional(
                    "scan_interval",
                    default=options.get("scan_interval", 10),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
            }
        )

        return self.async_show_form(
            step_id="options",
            data_schema=self.add_suggested_values_to_schema(options_schema, options),
        )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # Run the connection test entirely in the executor to avoid blocking calls
    try:
        await hass.async_add_executor_job(
            _test_connection,
            data[CONF_HOST],
            data[CONF_PORT],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
    except LoginError as err:
        _LOGGER.error("Authentication failed: %s", err)
        raise InvalidAuth from err
    except AmcrestError as err:
        _LOGGER.error("Cannot connect to camera: %s", err)
        raise CannotConnect from err

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_NAME]}


def _test_connection(host: str, port: int, username: str, password: str) -> None:
    """Test connection to camera in executor."""
    api = ApiWrapper(host, port, username, password)
    # Test the connection by getting current time
    _ = api.current_time


def _get_unique_id(host: str, port: int, username: str, password: str) -> str | None:
    """Get unique ID for camera in executor."""
    try:
        api = ApiWrapper(host, port, username, password)

        # Try to get serial number as unique ID
        try:
            serial = api.serial_number
            if serial:
                return str(serial)
        except AmcrestError:
            pass

    except AmcrestError:
        pass

    return None


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
