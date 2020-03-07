"""Config flow to configure the iCloud integration."""
import logging
import os

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudException, PyiCloudFailedLoginException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_MAX_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .const import DOMAIN  # pylint: disable=unused-import

CONF_TRUSTED_DEVICE = "trusted_device"
CONF_VERIFICATION_CODE = "verification_code"

_LOGGER = logging.getLogger(__name__)


class IcloudFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a iCloud config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize iCloud config flow."""
        self.api = None
        self._username = None
        self._password = None
        self._account_name = None
        self._max_interval = None
        self._gps_accuracy_threshold = None

        self._trusted_device = None
        self._verification_code = None

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        icloud_dir = self.hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

        if not os.path.exists(icloud_dir.path):
            await self.hass.async_add_executor_job(os.makedirs, icloud_dir.path)

        if user_input is None:
            return await self._show_setup_form(user_input, errors)

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        self._max_interval = user_input.get(CONF_MAX_INTERVAL, DEFAULT_MAX_INTERVAL)
        self._gps_accuracy_threshold = user_input.get(
            CONF_GPS_ACCURACY_THRESHOLD, DEFAULT_GPS_ACCURACY_THRESHOLD
        )

        # Check if already configured
        if self.unique_id is None:
            await self.async_set_unique_id(self._username)
            self._abort_if_unique_id_configured()

        try:
            self.api = await self.hass.async_add_executor_job(
                PyiCloudService, self._username, self._password, icloud_dir.path
            )
        except PyiCloudFailedLoginException as error:
            _LOGGER.error("Error logging into iCloud service: %s", error)
            self.api = None
            errors[CONF_USERNAME] = "login"
            return await self._show_setup_form(user_input, errors)

        if self.api.requires_2sa:
            return await self.async_step_trusted_device()

        return self.async_create_entry(
            title=self._username,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_MAX_INTERVAL: self._max_interval,
                CONF_GPS_ACCURACY_THRESHOLD: self._gps_accuracy_threshold,
            },
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    async def async_step_trusted_device(self, user_input=None, errors=None):
        """We need a trusted device."""
        if errors is None:
            errors = {}

        trusted_devices = await self.hass.async_add_executor_job(
            getattr, self.api, "trusted_devices"
        )
        trusted_devices_for_form = {}
        for i, device in enumerate(trusted_devices):
            trusted_devices_for_form[i] = device.get(
                "deviceName", f"SMS to {device.get('phoneNumber')}"
            )

        if user_input is None:
            return await self._show_trusted_device_form(
                trusted_devices_for_form, user_input, errors
            )

        self._trusted_device = trusted_devices[int(user_input[CONF_TRUSTED_DEVICE])]

        if not await self.hass.async_add_executor_job(
            self.api.send_verification_code, self._trusted_device
        ):
            _LOGGER.error("Failed to send verification code")
            self._trusted_device = None
            errors[CONF_TRUSTED_DEVICE] = "send_verification_code"

            return await self._show_trusted_device_form(
                trusted_devices_for_form, user_input, errors
            )

        return await self.async_step_verification_code()

    async def _show_trusted_device_form(
        self, trusted_devices, user_input=None, errors=None
    ):
        """Show the trusted_device form to the user."""

        return self.async_show_form(
            step_id=CONF_TRUSTED_DEVICE,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRUSTED_DEVICE): vol.All(
                        vol.Coerce(int), vol.In(trusted_devices)
                    )
                }
            ),
            errors=errors or {},
        )

    async def async_step_verification_code(self, user_input=None):
        """Ask the verification code to the user."""
        errors = {}

        if user_input is None:
            return await self._show_verification_code_form(user_input)

        self._verification_code = user_input[CONF_VERIFICATION_CODE]

        try:
            if not await self.hass.async_add_executor_job(
                self.api.validate_verification_code,
                self._trusted_device,
                self._verification_code,
            ):
                raise PyiCloudException("The code you entered is not valid.")
        except PyiCloudException as error:
            # Reset to the initial 2FA state to allow the user to retry
            _LOGGER.error("Failed to verify verification code: %s", error)
            self._trusted_device = None
            self._verification_code = None
            errors["base"] = "validate_verification_code"

            return await self.async_step_trusted_device(None, errors)

        return await self.async_step_user(
            {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_MAX_INTERVAL: self._max_interval,
                CONF_GPS_ACCURACY_THRESHOLD: self._gps_accuracy_threshold,
            }
        )

    async def _show_verification_code_form(self, user_input=None):
        """Show the verification_code form to the user."""

        return self.async_show_form(
            step_id=CONF_VERIFICATION_CODE,
            data_schema=vol.Schema({vol.Required(CONF_VERIFICATION_CODE): str}),
            errors=None,
        )
