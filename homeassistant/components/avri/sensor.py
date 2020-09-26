"""Support for Avri waste curbside collection pickup."""
import logging

from avri.api import Avri, AvriException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, DEVICE_CLASS_TIMESTAMP
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, ICON

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Avri Waste platform."""
    client = hass.data[DOMAIN][entry.entry_id]
    integration_id = entry.data[CONF_ID]

    try:
        each_upcoming = await hass.async_add_executor_job(client.upcoming_of_each)
    except AvriException as ex:
        raise PlatformNotReady from ex
    else:
        entities = [
            AvriWasteUpcoming(client, upcoming.name, integration_id)
            for upcoming in each_upcoming
        ]
        async_add_entities(entities, True)


class AvriWasteUpcoming(Entity):
    """Avri Waste Sensor."""

    def __init__(self, client: Avri, waste_type: str, integration_id: str):
        """Initialize the sensor."""
        self._waste_type = waste_type
        self._name = f"{self._waste_type}".title()
        self._state = None
        self._client = client
        self._state_available = False
        self._integration_id = integration_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return (f"{self._integration_id}" f"-{self._waste_type}").replace(" ", "")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state_available

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    async def async_update(self):
        """Update the data."""
        if not self.enabled:
            return

        try:
            pickup_events = self._client.upcoming_of_each()
        except AvriException as ex:
            _LOGGER.error(
                "There was an error retrieving upcoming garbage pickups: %s", ex
            )
            self._state_available = False
            self._state = None
        else:
            self._state_available = True
            matched_events = list(
                filter(lambda event: event.name == self._waste_type, pickup_events)
            )
            if not matched_events:
                self._state = None
            else:
                self._state = matched_events[0].day.date()
