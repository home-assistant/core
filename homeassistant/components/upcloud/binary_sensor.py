"""Support for monitoring the state of UpCloud servers."""

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from . import CONF_SERVERS, DATA_UPCLOUD, UpCloudServerEntity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [cv.string])}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Legacy platform set up."""
    _LOGGER.warning(
        "Loading upcloud binary sensors via platform config is deprecated and no longer "
        "necessary as of 0.114. Please remove it from binary_sensor YAML configuration."
    )
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the UpCloud server binary sensor."""
    coordinator = hass.data[DATA_UPCLOUD].coordinators[config_entry.data[CONF_USERNAME]]
    entities = [UpCloudBinarySensor(coordinator, uuid) for uuid in coordinator.data]
    async_add_entities(entities, True)


class UpCloudBinarySensor(UpCloudServerEntity, BinarySensorEntity):
    """Representation of an UpCloud server sensor."""
