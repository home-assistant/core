"""Binary sensor platform support for wiffi devices."""

from pathlib import Path

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import WiffiEntity
from .const import CREATE_ENTITY_SIGNAL, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up platform for a new integration.

    Called by the HA framework after async_forward_entry_setup has been called
    during initialization of a new integration (= wiffi).
    """
    stem = Path(__file__).stem  # stem = filename without py
    hass.data[DOMAIN][config_entry.entry_id].async_add_entities[
        stem
    ] = async_add_entities

    async_dispatcher_connect(hass, CREATE_ENTITY_SIGNAL, _create_entity)


@callback
def _create_entity(api, device, metric):
    """Create platform specific entities."""
    entities = []

    if metric.is_bool:
        entities.append(BoolEntity(device, metric))

    stem = Path(__file__).stem  # stem = filename without py
    api.async_add_entities[stem](entities)


class BoolEntity(WiffiEntity, BinarySensorDevice):
    """Entity for wiffi metrics which have a boolean value."""

    def __init__(self, device, metric):
        """Initialize the entity."""
        super().__init__(device, metric)
        self._value = metric.value
        self.reset_expiration_date()

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._value

    def _update_value(self, metric):
        """Update the value of the entity.

        Called if a new message has been received from the wiffi device.
        """
        self.reset_expiration_date()
        self._value = metric.value
        self.async_schedule_update_ha_state()
