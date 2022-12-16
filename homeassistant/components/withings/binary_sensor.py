"""Sensors flow for Withings."""
from __future__ import annotations

from withings_api.common import NotifyAppli

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import (
    BaseWithingsSensor,
    UpdateType,
    WithingsAttribute,
    async_get_data_manager,
)
from .const import Measurement

BINARY_SENSORS = [
    # Webhook measurements.
    WithingsAttribute(
        Measurement.IN_BED,
        NotifyAppli.BED_IN,
        "In bed",
        "",
        "mdi:bed",
        True,
        UpdateType.WEBHOOK,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    data_manager = await async_get_data_manager(hass, entry)

    entities = [
        WithingsHealthBinarySensor(data_manager, attribute)
        for attribute in BINARY_SENSORS
    ]

    async_add_entities(entities, True)


class WithingsHealthBinarySensor(BaseWithingsSensor, BinarySensorEntity):
    """Implementation of a Withings sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._state_data
