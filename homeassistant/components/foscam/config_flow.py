"""Config flow for foscam integration."""
from libpyfoscam import FoscamCamera
from libpyfoscam.foscam import ERROR_FOSCAM_AUTH, ERROR_FOSCAM_UNAVAILABLE
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from .const import CONF_STREAM, LOGGER
from .const import DOMAIN  # pylint:disable=unused-import

STREAMS = ["Main", "Sub"]

DEFAULT_PORT = 88


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_STREAM, default=STREAMS[0]): vol.In(STREAMS),
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    camera = FoscamCamera(
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        verbose=False,
    )

    # Validate data by sending a request to the camera
    ret, response = await hass.async_add_executor_job(camera.get_dev_info)

    if ret == ERROR_FOSCAM_UNAVAILABLE:
        raise CannotConnect

    if ret == ERROR_FOSCAM_AUTH:
        raise InvalidAuth

    return {CONF_NAME: response["devName"], CONF_MAC: response["mac"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for foscam."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"

            except InvalidAuth:
                errors["base"] = "invalid_auth"

            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(info[CONF_MAC])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config):
        """Handle config import from yaml."""
        try:
            info = await validate_input(self.hass, import_config)

        except CannotConnect:
            LOGGER.error("Error importing foscam platform config: cannot connect.")
            return self.async_abort(reason="cannot_connect")

        except InvalidAuth:
            LOGGER.error("Error importing foscam platform config: invalid auth.")
            return self.async_abort(reason="invalid_auth")

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                "Error importing foscam platform config: unexpected exception"
            )
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(info[CONF_MAC])
        self._abort_if_unique_id_configured()

        if CONF_NAME in import_config:
            info[CONF_NAME] = import_config.pop(CONF_NAME)

        return self.async_create_entry(title=info[CONF_NAME], data=import_config)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
