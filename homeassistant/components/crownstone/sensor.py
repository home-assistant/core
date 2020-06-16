"""Support for presence detection of Crownstone."""
import logging
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PRESENCE_LOCATION, PRESENCE_SPHERE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensor platform."""
    crownstone_hub = hass.data[DOMAIN][entry.entry_id]

    # add sphere presence entity
    entities = [
        Presence(
            crownstone_hub,
            crownstone_hub.sphere,
            PRESENCE_SPHERE["description"],
            PRESENCE_SPHERE["icon"],
        )
    ]
    # add location presence entities
    for location in crownstone_hub.sphere.locations:
        entities.append(
            Presence(
                crownstone_hub,
                location,
                PRESENCE_LOCATION["description"],
                PRESENCE_LOCATION["icon"],
            )
        )

    async_add_entities(entities, True)


class Presence(Entity):
    """
    Representation of a Presence Sensor.

    The state for this sensor is updated using the Crownstone SSE client running in the background.
    """

    def __init__(self, hub, presence_holder, description, icon):
        """Initialize the presence detector."""
        self.hub = hub
        self.presence_holder = presence_holder
        self.description = description
        self._icon = icon

    @property
    def name(self) -> str:
        """Return the name of this presence holder."""
        return self.presence_holder.name

    @property
    def icon(self) -> Optional[str]:
        """Return the icon."""
        return self._icon

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return self.presence_holder.unique_id

    @property
    def cloud_id(self) -> str:
        """Return the cloud id of this presence holder."""
        return self.presence_holder.cloud_id

    @property
    def state(self):
        """
        Return a friendly state of the presence detector.

        This state is a list of the first names represented as string.
        """
        _state = []
        for user_id in self.presence_holder.present_people:
            user = self.hub.sphere.users.find_by_id(user_id)
            _state.append(user.first_name)

        return ", ".join(_state)

    @property
    def state_attributes(self) -> Optional[Dict[str, Any]]:
        """
        State attributes for presence sensor.

        Contains more detailed information about the state.
        Currently it displays last name and role.
        """
        attributes = {}
        for user_id in self.presence_holder.present_people:
            user = self.hub.sphere.users.find_by_id(user_id)
            attributes[user.first_name] = (user.last_name, user.role)
        return attributes

    @property
    def available(self) -> bool:
        """Return if the presence sensor is available."""
        if self.hub.sse.state == "running":
            return True
        else:
            return False

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Crownstone",
            "model": self.description,
        }

    async def async_added_to_hass(self) -> None:
        """Set up a listener when this entity is added to HA."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )
