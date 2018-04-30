"""
Support for interacting with UpCloud servers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.upcloud/
"""
import logging

import voluptuous as vol

from homeassistant.const import STATE_OFF
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.components.upcloud import (
    UpCloudServerEntity, CONF_SERVERS, DATA_UPCLOUD)

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


class UpCloudSwitch(UpCloudServerEntity, SwitchDevice):
    """Representation of an UpCloud server switch."""

    def turn_on(self, **kwargs):
        """Start the server."""
        if self.state == STATE_OFF:
            self.data.start()

    def turn_off(self, **kwargs):
        """Stop the server."""
        if self.is_on:
            self.data.stop()
