"""
Support for interacting with UpCloud servers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.upcloud/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.components.upcloud import (
    UpCloudServerMixin, CONF_SERVERS, DATA_UPCLOUD)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['upcloud']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the UpCloud server switch."""
    upcloud = hass.data[DATA_UPCLOUD]

    servers = config.get(CONF_SERVERS)

    devices = [UpCloudSwitch(upcloud, uuid) for uuid in servers]

    add_devices(devices, True)


class UpCloudSwitch(UpCloudServerMixin, SwitchDevice):
    """Representation of an UpCloud server switch."""

    def __init__(self, upcloud, uuid):
        """Initialize a new UpCloud server switch."""
        UpCloudServerMixin.__init__(self, upcloud, uuid)

    def turn_on(self, **kwargs):
        """Start the server."""
        try:
            state = self.data.state
        except AttributeError:
            return
        if state == 'stopped':
            old_timeout = self.data.cloud_manager.timeout
            try:
                self.data.cloud_manager.timeout = None
                self.data.start()
            finally:
                self.data.cloud_manager.timeout = old_timeout

    def turn_off(self, **kwargs):
        """Stop the server."""
        try:
            state = self.data.state
        except AttributeError:
            return
        if state == 'started':
            self.data.stop()
