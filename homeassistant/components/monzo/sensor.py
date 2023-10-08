"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ACCOUNTS, CONF_COORDINATOR, DOMAIN, POTS
from .entity import MonzoBaseEntity


@dataclass
class MonzoSensorEntityDescriptionMixin:
    """Adds fields for Monzo sensors."""

    value: Callable[[dict[str, Any]], Any]


@dataclass
class MonzoSensorEntityDescription(
    SensorEntityDescription, MonzoSensorEntityDescriptionMixin
):
    """Describes Monzo sensor entity."""


ACC_SENSORS = (
    MonzoSensorEntityDescription(
        key="balance",
        name="Balance",
        value=lambda data: data["balance"]["balance"] / 100,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="£",
        suggested_display_precision=2,
    ),
    MonzoSensorEntityDescription(
        key="total_balance",
        name="Total Balance",
        value=lambda data: data["balance"]["total_balance"] / 100,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="£",
        suggested_display_precision=2,
    ),
)

POT_SENSORS = (
    MonzoSensorEntityDescription(
        key="pot_balance",
        name="Balance",
        value=lambda data: data["balance"] / 100,
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="£",
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][CONF_COORDINATOR]

    entities = []
    for index, account in enumerate(hass.data[DOMAIN][config_entry.entry_id][ACCOUNTS]):
        for entity_description in ACC_SENSORS:
            entities.append(
                MonzoSensor(
                    coordinator,
                    entity_description,
                    index,
                    account["name"],
                    lambda x: x["accounts"],
                )
            )

    for index, _pot in enumerate(hass.data[DOMAIN][config_entry.entry_id][POTS]):
        for entity_description in POT_SENSORS:
            entities.append(
                MonzoSensor(
                    coordinator, entity_description, index, "Pot", lambda x: x["pots"]
                )
            )

    async_add_entities(entities)


class MonzoSensor(MonzoBaseEntity, SensorEntity):
    """Represents a Monzo sensor."""

    entity_description: MonzoSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: MonzoSensorEntityDescription,
        index: int,
        device_model: str,
        data_accessor: Callable[
            [dict[str, list[dict[str, Any]]]], list[dict[str, Any]]
        ],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, index, device_model, data_accessor)
        self.entity_description = entity_description
        self._attr_name = f"{self.data['name']} {entity_description.name}"
        self._attr_unique_id = f"{self.data['id']}_{entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state."""

        try:
            state = self.entity_description.value(self.data)
        except (KeyError, ValueError):
            return None

        return cast(StateType, state)
