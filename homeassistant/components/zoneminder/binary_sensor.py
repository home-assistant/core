"""Support for ZoneMinder binary sensors."""

from zoneminder.zm import ZoneMinder

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ZoneMinderConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZoneMinderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ZoneMinder binary sensor platform."""
    async_add_entities(
        [
            ZMAvailabilitySensor(
                entry.data[CONF_HOST], entry.entry_id, entry.runtime_data.client
            )
        ]
    )


class ZMAvailabilitySensor(BinarySensorEntity):
    """Representation of the availability of ZoneMinder as a binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, host_name: str, entry_id: str, client: ZoneMinder) -> None:
        """Initialize availability sensor."""
        self._attr_name = host_name
        self._attr_unique_id = f"{entry_id}_availability"
        self._client = client

    def update(self) -> None:
        """Update the state of this sensor (availability of ZoneMinder)."""
        self._attr_is_on = self._client.is_available
