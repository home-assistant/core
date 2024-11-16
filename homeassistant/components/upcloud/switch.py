"""Support for interacting with UpCloud servers."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_UPCLOUD
from .entity import UpCloudServerEntity

SIGNAL_UPDATE_UPCLOUD = "upcloud_update"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UpCloud server switch."""
    coordinator = hass.data[DATA_UPCLOUD].coordinators[config_entry.data[CONF_USERNAME]]
    entities = [UpCloudSwitch(coordinator, uuid) for uuid in coordinator.data]
    async_add_entities(entities, True)


class UpCloudSwitch(UpCloudServerEntity, SwitchEntity):
    """Representation of an UpCloud server switch."""

    def turn_on(self, **kwargs: Any) -> None:
        """Start the server."""
        if self.state == STATE_OFF:
            self._server.start()
            dispatcher_send(self.hass, SIGNAL_UPDATE_UPCLOUD)

    def turn_off(self, **kwargs: Any) -> None:
        """Stop the server."""
        if self.is_on:
            self._server.stop()
