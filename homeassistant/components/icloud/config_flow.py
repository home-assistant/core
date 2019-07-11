"""Config flow to configure the iCloud integration."""
import logging
import os

import voluptuous as vol
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudException, PyiCloudFailedLoginException

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (CONF_ACCOUNTNAME, CONF_GPS_ACCURACY_THRESHOLD,
                    CONF_MAX_INTERVAL, DOMAIN)

_LOGGER = logging.getLogger(__name__)

_LOGGER.error('CONFIG_FLOW_ICLOUD')

@config_entries.HANDLERS.register(DOMAIN)
class IcloudFlowHandler(config_entries.ConfigFlow):
    """Handle a iCloud config flow."""

    _LOGGER.error('CONFIG_FLOW_ICLOUD:class')
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize iCloud config flow."""
        _LOGGER.error('CONFIG_FLOW_ICLOUD:init')
        self.api = None
        self.__username = None
        self.__password = None
        self._accountname = None
        self.__max_interval = None
        self.__gps_accuracy_threshold = None

        self.__trusted_device = None
        self.__verification_code = None

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""

        _LOGGER.error('CONFIG_FLOW_ICLOUD:form')
        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_ACCOUNTNAME): str,
                    vol.Optional(CONF_MAX_INTERVAL, default=30): int,
                    vol.Optional(CONF_GPS_ACCURACY_THRESHOLD, default=500): int,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""

        _LOGGER.error('CONFIG_FLOW_ICLOUD:user')
        icloud_dir = self.hass.config.path('icloud')
        if not os.path.exists(icloud_dir):
            os.makedirs(icloud_dir)

        if user_input is None:
            return await self._show_setup_form(user_input)

        self.__username = user_input[CONF_USERNAME]
        self.__password = user_input[CONF_PASSWORD]
        self._accountname = user_input[CONF_ACCOUNTNAME]
        self.__max_interval = user_input[CONF_MAX_INTERVAL]
        self.__gps_accuracy_threshold = user_input[CONF_GPS_ACCURACY_THRESHOLD]

        try:
            self.api = PyiCloudService(
                self.__username,
                self.__password,
                cookie_directory=icloud_dir,
                verify=True)
        except PyiCloudFailedLoginException as error:
            if self.api.requires_2fa:
                try:
                    if self.__trusted_device is None:
                        self.icloud_need_trusted_device()
                        return

                    if self.__verification_code is None:
                        self.icloud_need_verification_code()
                        return

                    self.api.authenticate()
                    if self.api.requires_2fa:
                        raise Exception('Unknown failure')

                    self.__trusted_device = None
                    self.__verification_code = None

                    return True
                except PyiCloudException as error:
                    _LOGGER.error("Error setting up 2FA: %s", error)
                    return False
            else:
                self.api = None
                _LOGGER.error("Error logging into iCloud Service: %s", error)
                return False
        return True

    async def async_step_final(self):
        """Handle the final step, create the config entry."""
        return self.async_create_entry(
            title=self._accountname,
            data={
                CONF_USERNAME: self.__username,
                CONF_PASSWORD: self.__password,
                CONF_ACCOUNTNAME: self._accountname,
                CONF_MAX_INTERVAL: self.__max_interval,
                CONF_GPS_ACCURACY_THRESHOLD: self.__gps_accuracy_threshold,
            },
        )

    def icloud_need_trusted_device(self):
        """We need a trusted device."""
        configurator = self.hass.components.configurator
        if self._accountname in _CONFIGURING:
            return

        devicesstring = ''
        devices = self.api.trusted_devices
        for i, device in enumerate(devices):
            devicename = device.get(
                'deviceName', 'SMS to %s' % device.get('phoneNumber'))
            devicesstring += "{}: {};".format(i, devicename)

        _CONFIGURING[self._accountname] = configurator.request_config(
            'iCloud {}'.format(self._accountname),
            self.icloud_trusted_device_callback,
            description=(
                'Please choose your trusted device by entering'
                ' the index from this list: ' + devicesstring),
            entity_picture="/static/images/config_icloud.png",
            submit_caption='Confirm',
            fields=[{'id': 'trusted_device', 'name': 'Trusted Device'}]
        )
    
    def icloud_trusted_device_callback(self, callback_data):
        """Handle chosen trusted devices."""
        self.__trusted_device = int(callback_data.get('trusted_device'))
        self.__trusted_device = self.api.trusted_devices[self.__trusted_device]

        if not self.api.send_verification_code(self.__trusted_device):
            _LOGGER.error("Failed to send verification code")
            self.__trusted_device = None
            return

        if self._accountname in _CONFIGURING:
            request_id = _CONFIGURING.pop(self._accountname)
            configurator = self.hass.components.configurator
            configurator.request_done(request_id)

        # Trigger the next step immediately
        self.icloud_need_verification_code()

    def icloud_need_verification_code(self):
        """Return the verification code."""
        configurator = self.hass.components.configurator
        if self._accountname in _CONFIGURING:
            return

        _CONFIGURING[self._accountname] = configurator.request_config(
            'iCloud {}'.format(self._accountname),
            self.icloud_verification_callback,
            description=('Please enter the validation code:'),
            entity_picture="/static/images/config_icloud.png",
            submit_caption='Confirm',
            fields=[{'id': 'code', 'name': 'code'}]
        )
    
    def icloud_verification_callback(self, callback_data):
        """Handle the chosen trusted device."""
        self.__verification_code = callback_data.get('code')

        try:
            if not self.api.validate_verification_code(
                    self.__trusted_device, self.__verification_code):
                raise PyiCloudException('Unknown failure')
        except PyiCloudException as error:
            # Reset to the initial 2FA state to allow the user to retry
            _LOGGER.error("Failed to verify verification code: %s", error)
            self.__trusted_device = None
            self.__verification_code = None

            # Trigger the next step immediately
            self.icloud_need_trusted_device()

        if self._accountname in _CONFIGURING:
            request_id = _CONFIGURING.pop(self._accountname)
            configurator = self.hass.components.configurator
            configurator.request_done(request_id)
