"""Config flow for ezviz."""
import logging

from pyezviz.client import EzvizClient
from pyezviz.exceptions import (
    AuthTestResultFailed,
    HTTPError,
    InvalidHost,
    InvalidURL,
    PyEzvizError,
)
from pyezviz.test_cam_rtsp import TestRTSPAuth
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import (
    CONF_CUSTOMIZE,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import callback

from .const import (
    ATTR_SERIAL,
    ATTR_TYPE_CAMERA,
    ATTR_TYPE_CLOUD,
    CONF_FFMPEG_ARGUMENTS,
    DEFAULT_CAMERA_USERNAME,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    EU_URL,
    RUSSIA_URL,
)

_LOGGER = logging.getLogger(__name__)


def _get_ezviz_client_instance(data):
    """Initialize a new instance of EzvizClientApi."""

    ezviz_client = EzvizClient(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data.get(CONF_URL, EU_URL),
        data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
    )

    ezviz_client.login()
    return ezviz_client


def _test_camera_rtsp_creds(data):
    """Try DESCRIBE on RTSP camera with credentials."""

    test_rtsp = TestRTSPAuth(
        data[CONF_IP_ADDRESS], data[CONF_USERNAME], data[CONF_PASSWORD]
    )

    test_rtsp.main()


class EzvizConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ezviz."""

    VERSION = 1

    async def _validate_and_create_auth(self, data):
        """Try to login to ezviz cloud account and create entry if successful."""
        await self.async_set_unique_id(data[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        # Verify cloud credentials by attempting a login request.
        try:
            await self.hass.async_add_executor_job(_get_ezviz_client_instance, data)

        except InvalidURL as err:
            raise InvalidURL from err

        except HTTPError as err:
            raise InvalidHost from err

        except PyEzvizError as err:
            raise PyEzvizError from err

        auth_data = {
            CONF_USERNAME: data[CONF_USERNAME],
            CONF_PASSWORD: data[CONF_PASSWORD],
            CONF_URL: data.get(CONF_URL, EU_URL),
            CONF_TYPE: ATTR_TYPE_CLOUD,
        }

        return self.async_create_entry(title=data[CONF_USERNAME], data=auth_data)

    async def _validate_and_create_camera_rtsp(self, data):
        """Try DESCRIBE on RTSP camera with credentials."""

        # Get Ezviz cloud credentials from config entry
        ezviz_client_creds = {
            CONF_USERNAME: None,
            CONF_PASSWORD: None,
            CONF_URL: None,
        }

        for item in self._async_current_entries():
            if item.data.get(CONF_TYPE) == ATTR_TYPE_CLOUD:
                ezviz_client_creds = {
                    CONF_USERNAME: item.data.get(CONF_USERNAME),
                    CONF_PASSWORD: item.data.get(CONF_PASSWORD),
                    CONF_URL: item.data.get(CONF_URL),
                }

        # Abort flow if user removed cloud account before adding camera.
        if ezviz_client_creds[CONF_USERNAME] is None:
            return self.async_abort(reason="ezviz_cloud_account_missing")

        # We need to wake hibernating cameras.
        # First create EZVIZ API instance.
        try:
            ezviz_client = await self.hass.async_add_executor_job(
                _get_ezviz_client_instance, ezviz_client_creds
            )

        except InvalidURL as err:
            raise InvalidURL from err

        except HTTPError as err:
            raise InvalidHost from err

        except PyEzvizError as err:
            raise PyEzvizError from err

        # Secondly try to wake hybernating camera.
        try:
            await self.hass.async_add_executor_job(
                ezviz_client.get_detection_sensibility, data[ATTR_SERIAL]
            )

        except HTTPError as err:
            raise InvalidHost from err

        # Thirdly attempts an authenticated RTSP DESCRIBE request.
        try:
            await self.hass.async_add_executor_job(_test_camera_rtsp_creds, data)

        except InvalidHost as err:
            raise InvalidHost from err

        except AuthTestResultFailed as err:
            raise AuthTestResultFailed from err

        return self.async_create_entry(
            title=data[ATTR_SERIAL],
            data={
                CONF_USERNAME: data[CONF_USERNAME],
                CONF_PASSWORD: data[CONF_PASSWORD],
                CONF_TYPE: ATTR_TYPE_CAMERA,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return EzvizOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        # Check if ezviz cloud account is present in entry config,
        # abort if already configured.
        for item in self._async_current_entries():
            if item.data.get(CONF_TYPE) == ATTR_TYPE_CLOUD:
                return self.async_abort(reason="already_configured_account")

        errors = {}

        if user_input is not None:

            if user_input[CONF_URL] == CONF_CUSTOMIZE:
                self.context["data"] = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
                return await self.async_step_user_custom_url()

            if CONF_TIMEOUT not in user_input:
                user_input[CONF_TIMEOUT] = DEFAULT_TIMEOUT

            try:
                return await self._validate_and_create_auth(user_input)

            except InvalidURL:
                errors["base"] = "invalid_host"

            except InvalidHost:
                errors["base"] = "cannot_connect"

            except PyEzvizError:
                errors["base"] = "invalid_auth"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_URL, default=EU_URL): vol.In(
                    [EU_URL, RUSSIA_URL, CONF_CUSTOMIZE]
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_user_custom_url(self, user_input=None):
        """Handle a flow initiated by the user for custom region url."""

        errors = {}

        if user_input is not None:
            user_input[CONF_USERNAME] = self.context["data"][CONF_USERNAME]
            user_input[CONF_PASSWORD] = self.context["data"][CONF_PASSWORD]

            if CONF_TIMEOUT not in user_input:
                user_input[CONF_TIMEOUT] = DEFAULT_TIMEOUT

            try:
                return await self._validate_and_create_auth(user_input)

            except InvalidURL:
                errors["base"] = "invalid_host"

            except InvalidHost:
                errors["base"] = "cannot_connect"

            except PyEzvizError:
                errors["base"] = "invalid_auth"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

        data_schema_custom_url = vol.Schema(
            {
                vol.Required(CONF_URL, default=EU_URL): str,
            }
        )

        return self.async_show_form(
            step_id="user_custom_url", data_schema=data_schema_custom_url, errors=errors
        )

    async def async_step_discovery(self, discovery_info):
        """Handle a flow for discovered camera without rtsp config entry."""

        await self.async_set_unique_id(discovery_info[ATTR_SERIAL])
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"serial": self.unique_id}
        self.context["data"] = {CONF_IP_ADDRESS: discovery_info[CONF_IP_ADDRESS]}

        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Confirm and create entry from discovery step."""
        errors = {}

        if user_input is not None:
            user_input[ATTR_SERIAL] = self.unique_id
            user_input[CONF_IP_ADDRESS] = self.context["data"][CONF_IP_ADDRESS]
            try:
                return await self._validate_and_create_camera_rtsp(user_input)

            except (InvalidHost, InvalidURL):
                errors["base"] = "invalid_host"

            except (PyEzvizError, AuthTestResultFailed):
                errors["base"] = "invalid_auth"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")

        discovered_camera_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=DEFAULT_CAMERA_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="confirm",
            data_schema=discovered_camera_schema,
            errors=errors,
            description_placeholders={
                "serial": self.unique_id,
                CONF_IP_ADDRESS: self.context["data"][CONF_IP_ADDRESS],
            },
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

        except InvalidURL:
            _LOGGER.error("Error importing Ezviz platform config: invalid host")
            return self.async_abort(reason="invalid_host")

        except InvalidHost:
            _LOGGER.error("Error importing Ezviz platform config: cannot connect")
            return self.async_abort(reason="cannot_connect")

        except (AuthTestResultFailed, PyEzvizError):
            _LOGGER.error("Error importing Ezviz platform config: invalid auth")
            return self.async_abort(reason="invalid_auth")

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
