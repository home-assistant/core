"""Support for israel rail."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Literal, get_args

from homeassistant import config_entries, core
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DEPARTURES_COUNT, DOMAIN
from .coordinator import DataConnection, IsraelRailDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSORS = Literal["duration", "platform", "transfers", "train_number"]


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        IsraelRailDepartureSensor(coordinator, i) for i in range(DEPARTURES_COUNT)
    ] + [IsraelRailSensor(coordinator, sensor) for sensor in get_args(SENSORS)]
    async_add_entities(entities)


class IsraelRailEntitySensor(
    CoordinatorEntity[IsraelRailDataUpdateCoordinator], SensorEntity
):
    """Define a Israel Rail sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _index: int = 0
    _value_fn: Callable[[DataConnection], StateType | datetime]

    def __init__(
        self,
        coordinator: IsraelRailDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self._value_fn(self.coordinator.data[self._index])


class IsraelRailDepartureSensor(IsraelRailEntitySensor):
    """Implementation of a Israel Rail departure sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: IsraelRailDataUpdateCoordinator,
        index: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._index = index
        self._attr_translation_key = f"departure{index}"
        self._value_fn = lambda data_connection: data_connection["departure"]
        self._attr_unique_id = f"{coordinator.unique_id}_departure{index}"
        departure_data = self.coordinator.data[self._index]
        self._attr_extra_state_attributes = {
            "start": departure_data["start"],
            "destination": departure_data["destination"],
        }


class IsraelRailSensor(IsraelRailEntitySensor):
    """Implementation of a Israel Rail other sensor."""

    def __init__(
        self,
        coordinator: IsraelRailDataUpdateCoordinator,
        other: SENSORS,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_translation_key = other
        self._other = other
        self._attr_unique_id = f"{coordinator.unique_id}_{other}"
        self._value_fn = lambda data_connection: data_connection[other]
