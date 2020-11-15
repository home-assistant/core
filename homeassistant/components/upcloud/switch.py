"""Support for interacting with UpCloud servers."""

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_USERNAME, STATE_OFF
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send

from . import CONF_SERVERS, DATA_UPCLOUD, SIGNAL_UPDATE_UPCLOUD, UpCloudServerEntity

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [cv.string])}
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the UpCloud server switch."""
    coordinator = hass.data[DATA_UPCLOUD].coordinators[config_entry.data[CONF_USERNAME]]
    entities = [UpCloudSwitch(coordinator, uuid) for uuid in coordinator.data]
    async_add_entities(entities, True)


class UpCloudSwitch(UpCloudServerEntity, SwitchEntity):
    """Representation of an UpCloud server switch."""

    def turn_on(self, **kwargs):
        """Start the server."""
        if self.state == STATE_OFF:
            self._server.start()
            dispatcher_send(self.hass, SIGNAL_UPDATE_UPCLOUD)

    def turn_off(self, **kwargs):
        """Stop the server."""
        if self.is_on:
            self._server.stop()
