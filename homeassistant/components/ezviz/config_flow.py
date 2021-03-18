"""Config flow for ezviz."""
import logging

from pyezviz import EzvizClient
from pyezviz.client import PyEzvizError
from requests.exceptions import HTTPError
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_REGION,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import (  # pylint: disable=unused-import
    ATTR_SERIAL,
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
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
        """Try to login to ezviz cloud account and create entry if successful."""
        await self.async_set_unique_id(data[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        client = EzvizClient(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data.get(CONF_REGION, DEFAULT_REGION),
            data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        )

        # Attempts a login request.
        try:
            await self.hass.async_add_executor_job(client.login)

        except (PyEzvizError, HTTPError) as err:
            raise InvalidAuth from err

        auth_data = {
            CONF_USERNAME: data[CONF_USERNAME],
            CONF_PASSWORD: data[CONF_PASSWORD],
            CONF_REGION: data.get(CONF_REGION, DEFAULT_REGION),
            CONF_TYPE: ATTR_TYPE_CLOUD,
        }

        return self.async_create_entry(title=data[CONF_USERNAME], data=auth_data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return EzvizOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        # Check if ezviz cloud account is present in entry config.
        # Return camera user flow if present.
        for item in self._async_current_entries():
            if item.data.get(CONF_TYPE) == ATTR_TYPE_CLOUD:
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
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_TYPE: ATTR_TYPE_CAMERA,
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

    async def async_step_discovery(self, discovery_info):
        """Handle a flow for discovered camera without rtsp config entry."""

        await self.async_set_unique_id(discovery_info[ATTR_SERIAL])
        self._abort_if_unique_id_configured()

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Confirm and create entry from discovery step."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=self.unique_id,
                data={
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_TYPE: ATTR_TYPE_CAMERA,
                },
            )

        discovered_camera_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=DEFAULT_CAMERA_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"serial": self.unique_id},
            data_schema=discovered_camera_schema,
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Handle config import from yaml."""
        _LOGGER.debug("import config: %s", import_config)

        # Check importing camera.
        if ATTR_SERIAL in import_config:
            return await self.async_step_import_camera(import_config)

        # Validate and setup of main ezviz cloud account.
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

    async def async_step_import_camera(self, data):
        """Create RTSP auth entry per camera in config."""

        await self.async_set_unique_id(data[ATTR_SERIAL])
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Create camera with: %s", data)

        cam_serial = data.pop(ATTR_SERIAL)
        data[CONF_TYPE] = ATTR_TYPE_CAMERA

        return self.async_create_entry(title=cam_serial, data=data)


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
