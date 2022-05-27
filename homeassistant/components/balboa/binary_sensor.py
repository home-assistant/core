"""Support for Balboa Spa binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CIRC_PUMP, DOMAIN, FILTER
from .entity import BalboaEntity

FILTER_STATES = [
    [False, False],  # self.FILTER_OFF
    [True, False],  # self.FILTER_1
    [False, True],  # self.FILTER_2
    [True, True],  # self.FILTER_1_2
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa's binary sensors."""
    spa = hass.data[DOMAIN][entry.entry_id]
    entities: list[BalboaSpaBinarySensor] = [
        BalboaSpaFilter(entry, spa, FILTER, index) for index in range(1, 3)
    ]
    if spa.have_circ_pump():
        entities.append(BalboaSpaCircPump(entry, spa, CIRC_PUMP))

    async_add_entities(entities)


class BalboaSpaBinarySensor(BalboaEntity, BinarySensorEntity):
    """Representation of a Balboa Spa binary sensor entity."""

    _attr_device_class = BinarySensorDeviceClass.MOVING


class BalboaSpaCircPump(BalboaSpaBinarySensor):
    """Representation of a Balboa Spa circulation pump."""

    @property
    def is_on(self) -> bool:
        """Return true if the filter is on."""
        return self._client.get_circ_pump()

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:water-pump" if self.is_on else "mdi:water-pump-off"


class BalboaSpaFilter(BalboaSpaBinarySensor):
    """Representation of a Balboa Spa Filter."""

    @property
    def is_on(self) -> bool:
        """Return true if the filter is on."""
        return FILTER_STATES[self._client.get_filtermode()][self._num - 1]

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:sync" if self.is_on else "mdi:sync-off"
