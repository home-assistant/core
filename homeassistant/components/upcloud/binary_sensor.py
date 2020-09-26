"""Support for monitoring the state of UpCloud servers."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
import homeassistant.helpers.config_validation as cv

from . import CONF_SERVERS, DATA_UPCLOUD, UpCloudServerEntity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [cv.string])}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the UpCloud server binary sensor."""
    upcloud = hass.data[DATA_UPCLOUD]

    servers = config.get(CONF_SERVERS)

    devices = [UpCloudBinarySensor(upcloud, uuid) for uuid in servers]

    add_entities(devices, True)


class UpCloudBinarySensor(UpCloudServerEntity, BinarySensorEntity):
    """Representation of an UpCloud server sensor."""
