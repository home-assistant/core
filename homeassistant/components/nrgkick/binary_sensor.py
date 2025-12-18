"""Binary sensor platform for NRGkick."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NRGkickConfigEntry, NRGkickDataUpdateCoordinator, NRGkickEntity
from .const import STATUS_CHARGING

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick binary sensors based on a config entry."""
    coordinator: NRGkickDataUpdateCoordinator = entry.runtime_data

    entities: list[NRGkickBinarySensor] = [
        NRGkickBinarySensor(
            coordinator,
            key="charging",
            device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
            value_path=["values", "general", "status"],
            value_fn=lambda x: (
                x == STATUS_CHARGING if isinstance(x, int) else x == "CHARGING"
            ),
        ),
        NRGkickBinarySensor(
            coordinator,
            key="charge_permitted",
            device_class=BinarySensorDeviceClass.POWER,
            value_path=["values", "general", "charge_permitted"],
        ),
        NRGkickBinarySensor(
            coordinator,
            key="charge_pause",
            device_class=None,
            value_path=["control", "charge_pause"],
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ]

    async_add_entities(entities)


class NRGkickBinarySensor(NRGkickEntity, BinarySensorEntity):
    """Representation of a NRGkick binary sensor."""

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        *,
        key: str,
        device_class: BinarySensorDeviceClass | None,
        value_path: list[str],
        entity_category: EntityCategory | None = None,
        value_fn: Callable[[Any], bool] | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, key)
        self._attr_device_class = device_class
        self._value_path = value_path
        self._attr_entity_category = entity_category
        self._value_fn = value_fn

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        data: Any = self.coordinator.data
        for key in self._value_path:
            if data is None:
                return None
            data = data.get(key)

        if self._value_fn and data is not None:
            return self._value_fn(data)
        return bool(data)
