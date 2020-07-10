"""Support for interacting with UpCloud servers."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import STATE_OFF
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send

from . import CONF_SERVERS, DATA_UPCLOUD, SIGNAL_UPDATE_UPCLOUD, UpCloudServerEntity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [cv.string])}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Legacy platform set up."""
    _LOGGER.warning(
        "Loading upcloud switches via platform config is deprecated and no longer "
        "necessary as of 0.114. Please remove it from switch YAML configuration."
    )
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the UpCloud server switch."""
    devices = []
    for data in hass.data[DATA_UPCLOUD].values():
        devices.extend(UpCloudSwitch(data.upcloud, uuid) for uuid in data.upcloud.data)
    async_add_entities(devices, True)


class UpCloudSwitch(UpCloudServerEntity, SwitchEntity):
    """Representation of an UpCloud server switch."""

    def turn_on(self, **kwargs):
        """Start the server."""
        if self.state == STATE_OFF:
            self.data.start()
            dispatcher_send(self.hass, SIGNAL_UPDATE_UPCLOUD)

    def turn_off(self, **kwargs):
        """Stop the server."""
        if self.is_on:
            self.data.stop()
