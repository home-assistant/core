"""Config flow for ezviz."""
import logging

from pyezviz import EzvizClient
from pyezviz.client import PyEzvizError
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import (  # pylint: disable=unused-import
    ATTR_CAMERAS,
    ATTR_SERIAL,
    CONF_FFMPEG_ARGUMENTS,
    DEFAULT_CAMERA_USERNAME,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_REGION,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class EzvizConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ezviz."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_CLOUD_POLL

    async def _validate_and_create_auth(self, data):
        """Validate the user input allows us to connect.

        Data has the keys from data_schema with values provided by the user.
        """
        await self.async_set_unique_id(data[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        # constructor does login call
        client = EzvizClient(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data.get(CONF_REGION, DEFAULT_REGION),
            data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        )

        # Validate data by sending a login request to ezviz

        try:
            await self.hass.async_add_executor_job(client.login)

        except PyEzvizError as err:
            raise InvalidAuth from err

        auth_data = {
            "username": data[CONF_USERNAME],
            "password": data[CONF_PASSWORD],
            "region": data.get(CONF_REGION, DEFAULT_REGION),
        }

        return self.async_create_entry(title=data[CONF_USERNAME], data=auth_data)

    async def _create_camera_rstp(self, data):
        """Create RSTP auth entry per camera in config."""

        await self.async_set_unique_id(data[0])
        self._abort_if_unique_id_configured()

        camera_rstp_creds = {
            ATTR_SERIAL: data[0],
            CONF_USERNAME: data[1][CONF_USERNAME],
            CONF_PASSWORD: data[1][CONF_PASSWORD],
        }

        _LOGGER.debug("Create camera with: %s", camera_rstp_creds)

        return self.async_create_entry(title=data[0], data=camera_rstp_creds)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return EzvizOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return await self.async_step_user_camera()

        errors = {}

        if user_input is not None:
            if CONF_TIMEOUT not in user_input:
                user_input[CONF_TIMEOUT] = DEFAULT_TIMEOUT

            try:
                return await self._validate_and_create_auth(user_input)

            except InvalidAuth:
                errors["base"] = "invalid_auth"

            except AbortFlow:
                raise

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_REGION, default=DEFAULT_REGION): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors or {}
        )

    async def async_step_user_camera(self, user_input=None):
        """Handle a flow initiated by the user."""

        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[ATTR_SERIAL])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[ATTR_SERIAL],
                data={
                    ATTR_SERIAL: user_input[ATTR_SERIAL],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                },
            )

        camera_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=DEFAULT_CAMERA_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(ATTR_SERIAL): str,
            }
        )

        return self.async_show_form(
            step_id="user_camera", data_schema=camera_schema, errors=errors or {}
        )

    async def async_step_import(self, import_config):
        """Handle config import from yaml."""
        _LOGGER.debug("import config: %s", import_config)

        if ATTR_CAMERAS in import_config:
            try:
                return await self._validate_and_create_auth(import_config)

            except InvalidAuth:
                _LOGGER.error("Error importing Ezviz platform config: invalid auth")
                return self.async_abort(reason="invalid_auth")

            except AbortFlow:
                raise

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Error importing ezviz platform config: unexpected exception"
                )
            return self.async_abort(reason="unknown")

        if ATTR_CAMERAS not in import_config:
            try:
                return await self._create_camera_rstp(import_config)

            except AbortFlow:
                raise

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Error importing ezviz platform config: unexpected exception"
                )
            return self.async_abort(reason="unknown")


class EzvizOptionsFlowHandler(OptionsFlow):
    """Handle Ezviz client options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage Ezviz options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_TIMEOUT,
                default=self.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): int,
            vol.Optional(
                CONF_FFMPEG_ARGUMENTS,
                default=self.config_entry.options.get(
                    CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
                ),
            ): str,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
