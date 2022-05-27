"""Config flow for foscam integration."""
from libpyfoscam import FoscamCamera
from libpyfoscam.foscam import (
    ERROR_FOSCAM_AUTH,
    ERROR_FOSCAM_UNAVAILABLE,
    FOSCAM_SUCCESS,
)
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import AbortFlow

from .const import CONF_RTSP_PORT, CONF_STREAM, DOMAIN, LOGGER

STREAMS = ["Main", "Sub"]

DEFAULT_PORT = 88
DEFAULT_RTSP_PORT = 554


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_STREAM, default=STREAMS[0]): vol.In(STREAMS),
        vol.Required(CONF_RTSP_PORT, default=DEFAULT_RTSP_PORT): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for foscam."""

    VERSION = 2

    async def _validate_and_create(self, data):
        """Validate the user input allows us to connect.

        Data has the keys from DATA_SCHEMA with values provided by the user.
        """
        self._async_abort_entries_match(
            {CONF_HOST: data[CONF_HOST], CONF_PORT: data[CONF_PORT]}
        )

        camera = FoscamCamera(
            data[CONF_HOST],
            data[CONF_PORT],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            verbose=False,
        )

        # Validate data by sending a request to the camera
        ret, _ = await self.hass.async_add_executor_job(camera.get_product_all_info)

        if ret == ERROR_FOSCAM_UNAVAILABLE:
            raise CannotConnect

        if ret == ERROR_FOSCAM_AUTH:
            raise InvalidAuth

        if ret != FOSCAM_SUCCESS:
            LOGGER.error(
                "Unexpected error code from camera %s:%s: %s",
                data[CONF_HOST],
                data[CONF_PORT],
                ret,
            )
            raise InvalidResponse

        # Try to get camera name (only possible with admin account)
        ret, response = await self.hass.async_add_executor_job(camera.get_dev_info)

        dev_name = response.get(
            "devName", f"Foscam {data[CONF_HOST]}:{data[CONF_PORT]}"
        )

        name = data.pop(CONF_NAME, dev_name)

        return self.async_create_entry(title=name, data=data)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                return await self._validate_and_create(user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"

            except InvalidAuth:
                errors["base"] = "invalid_auth"

            except InvalidResponse:
                errors["base"] = "invalid_response"

            except AbortFlow:
                raise

            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidResponse(exceptions.HomeAssistantError):
    """Error to indicate there is invalid response."""
