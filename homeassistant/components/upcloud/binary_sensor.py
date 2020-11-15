"""Support for monitoring the state of UpCloud servers."""

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from . import CONF_SERVERS, DATA_UPCLOUD, UpCloudServerEntity

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [cv.string])}
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the UpCloud server binary sensor."""
    coordinator = hass.data[DATA_UPCLOUD].coordinators[config_entry.data[CONF_USERNAME]]
    entities = [UpCloudBinarySensor(coordinator, uuid) for uuid in coordinator.data]
    async_add_entities(entities, True)


class UpCloudBinarySensor(UpCloudServerEntity, BinarySensorEntity):
    """Representation of an UpCloud server sensor."""
