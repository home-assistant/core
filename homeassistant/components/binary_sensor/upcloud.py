"""
Support for monitoring the state of UpCloud servers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.upcloud/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.upcloud import (
    UpCloudServerEntity, CONF_SERVERS, DATA_UPCLOUD)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['upcloud']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the UpCloud server binary sensor."""
    upcloud = hass.data[DATA_UPCLOUD]

    servers = config.get(CONF_SERVERS)

    devices = [UpCloudBinarySensor(upcloud, uuid) for uuid in servers]

    add_entities(devices, True)


class UpCloudBinarySensor(UpCloudServerEntity, BinarySensorDevice):
    """Representation of an UpCloud server sensor."""
