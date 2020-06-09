"""Binary sensor platform support for wiffi devices."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import WiffiEntity
from .const import CREATE_ENTITY_SIGNAL


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up platform for a new integration.

    Called by the HA framework after async_forward_entry_setup has been called
    during initialization of a new integration (= wiffi).
    """

    @callback
    def _create_entity(device, metric):
        """Create platform specific entities."""
        entities = []

        if metric.is_bool:
            entities.append(BoolEntity(device, metric))

        async_add_entities(entities)

    async_dispatcher_connect(hass, CREATE_ENTITY_SIGNAL, _create_entity)


class BoolEntity(WiffiEntity, BinarySensorEntity):
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

    @callback
    def _update_value_callback(self, device, metric):
        """Update the value of the entity.

        Called if a new message has been received from the wiffi device.
        """
        self.reset_expiration_date()
        self._value = metric.value
        self.async_write_ha_state()
