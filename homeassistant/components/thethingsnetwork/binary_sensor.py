"""The Things Network's integration binary sensors."""

from ttn_client import TTN_BaseValue, TTN_BinarySensorValue

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .const import OPTIONS_FIELD_ENTITY_TYPE_BINARY_SENSOR
from .entity import TTN_Entity
from .entry_settings import TTN_EntrySettings


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Add entities for TTN."""

    entry.coordinator.register_platform_entity_class(TtnBinarySensor, async_add_entities)
    entry.coordinator.async_add_entities()


async def async_unload_entry(hass: HomeAssistant, entry, async_remove_entity) -> None:
    """Handle removal of an entry."""


class TtnBinarySensor(TTN_Entity, SensorEntity):
    """Represents a TTN Home Assistant BinarySensor."""

    @staticmethod
    def manages_uplink(entrySettings: TTN_EntrySettings, ttn_value: TTN_BaseValue):
        """Check if this class maps to this ttn_value."""

        entity_type = entrySettings.get_entity_type(
            ttn_value.device_id, ttn_value.field_id
        )

        if entity_type:
            return entity_type == OPTIONS_FIELD_ENTITY_TYPE_BINARY_SENSOR
        else:
            return isinstance(ttn_value, TTN_BinarySensorValue)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return bool(super(TTN_Entity, self).state)

    @TTN_Entity.state.getter
    def state(self):
        """Return the state of the binary sensor."""
        return STATE_ON if self.is_on else STATE_OFF
