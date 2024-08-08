"""Binary sensor platform support for wiffi devices."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WiffiEntity
from .const import CREATE_ENTITY_SIGNAL


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up platform for a new integration.

    Called by the HA framework after async_forward_entry_setups has been called
    during initialization of a new integration (= wiffi).
    """

    @callback
    def _create_entity(device, metric):
        """Create platform specific entities."""
        entities = []

        if metric.is_bool:
            entities.append(BoolEntity(device, metric, config_entry.options))

        async_add_entities(entities)

    async_dispatcher_connect(hass, CREATE_ENTITY_SIGNAL, _create_entity)


class BoolEntity(WiffiEntity, BinarySensorEntity):
    """Entity for wiffi metrics which have a boolean value."""

    def __init__(self, device, metric, options):
        """Initialize the entity."""
        super().__init__(device, metric, options)
        self._attr_is_on = metric.value
        self.reset_expiration_date()

    @property
    def available(self):
        """Return true if value is valid."""
        return self._attr_is_on is not None

    @callback
    def _update_value_callback(self, device, metric):
        """Update the value of the entity.

        Called if a new message has been received from the wiffi device.
        """
        self.reset_expiration_date()
        self._attr_is_on = metric.value
        self.async_write_ha_state()
