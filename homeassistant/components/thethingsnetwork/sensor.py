"""The Things Network's integration sensors."""

from typing import Optional

from ttn_client import TTN_BaseValue, TTN_SensorValue

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .const import OPTIONS_FIELD_ENTITY_TYPE_SENSOR
from .entity import TTN_Entity
from .entry_settings import TTN_EntrySettings


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Add entities for TTN."""

    entry.coordinator.register_platform_entity_class(TtnDataSensor, async_add_entities)
    entry.coordinator.async_add_entities()


async def async_unload_entry(hass: HomeAssistant, entry, async_remove_entity) -> None:
    """Handle removal of an entry."""


class TtnDataSensor(TTN_Entity, SensorEntity):
    """Represents a TTN Home Assistant Sensor."""

    @staticmethod
    def manages_uplink(entrySettings: TTN_EntrySettings, ttn_value: TTN_BaseValue):
        """Check if this class maps to this ttn_value."""

        entity_type = entrySettings.get_entity_type(
            ttn_value.device_id, ttn_value.field_id
        )

        if entity_type:
            return entity_type == OPTIONS_FIELD_ENTITY_TYPE_SENSOR
        else:
            return isinstance(ttn_value, TTN_SensorValue)

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement
