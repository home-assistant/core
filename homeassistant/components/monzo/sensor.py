"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MonzoCoordinator
from .const import DOMAIN
from .coordinator import MonzoData
from .entity import MonzoBaseEntity


@dataclass(frozen=True, kw_only=True)
class MonzoSensorEntityDescription(SensorEntityDescription):
    """Describes Monzo sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]


ACCOUNT_SENSORS = (
    MonzoSensorEntityDescription(
        key="balance",
        translation_key="balance",
        value_fn=lambda data: data["balance"]["balance"] / 100,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="GBP",
        suggested_display_precision=2,
    ),
    MonzoSensorEntityDescription(
        key="total_balance",
        translation_key="total_balance",
        value_fn=lambda data: data["balance"]["total_balance"] / 100,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="GBP",
        suggested_display_precision=2,
    ),
)

POT_SENSORS = (
    MonzoSensorEntityDescription(
        key="pot_balance",
        translation_key="pot_balance",
        value_fn=lambda data: data["balance"] / 100,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="GBP",
        suggested_display_precision=2,
    ),
)

MODEL_POT = "Pot"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator: MonzoCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    accounts = [
        MonzoSensor(
            coordinator,
            entity_description,
            index,
            account["name"],
            lambda x: x.accounts,
        )
        for entity_description in ACCOUNT_SENSORS
        for index, account in enumerate(coordinator.data.accounts)
    ]

    pots = [
        MonzoSensor(coordinator, entity_description, index, MODEL_POT, lambda x: x.pots)
        for entity_description in POT_SENSORS
        for index, _pot in enumerate(coordinator.data.pots)
    ]

    async_add_entities(accounts + pots)


class MonzoSensor(MonzoBaseEntity, SensorEntity):
    """Represents a Monzo sensor."""

    entity_description: MonzoSensorEntityDescription

    def __init__(
        self,
        coordinator: MonzoCoordinator,
        entity_description: MonzoSensorEntityDescription,
        index: int,
        device_model: str,
        data_accessor: Callable[[MonzoData], list[dict[str, Any]]],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, index, device_model, data_accessor)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self.data['id']}_{entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state."""

        try:
            state = self.entity_description.value_fn(self.data)
        except (KeyError, ValueError):
            return None

        return state
