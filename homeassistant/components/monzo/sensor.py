"""Platform for sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import MonzoConfigEntry, MonzoCoordinator, MonzoData
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
    config_entry: MonzoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = config_entry.runtime_data

    accounts = [
        MonzoSensor(
            coordinator,
            entity_description,
            account_id,
            account["name"],
            lambda x: x.accounts,
        )
        for entity_description in ACCOUNT_SENSORS
        for account_id, account in coordinator.data.accounts.items()
    ]

    pots = [
        MonzoSensor(
            coordinator, entity_description, pot_id, MODEL_POT, lambda x: x.pots
        )
        for entity_description in POT_SENSORS
        for pot_id in coordinator.data.pots
    ]

    async_add_entities(accounts + pots)


class MonzoSensor(MonzoBaseEntity, SensorEntity):
    """Represents a Monzo sensor."""

    entity_description: MonzoSensorEntityDescription

    def __init__(
        self,
        coordinator: MonzoCoordinator,
        entity_description: MonzoSensorEntityDescription,
        resource_id: str,
        device_model: str,
        data_accessor: Callable[[MonzoData], dict[str, dict[str, Any]]],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, resource_id, device_model, data_accessor)
        self.entity_description = entity_description
        self._attr_unique_id = f"{resource_id}_{entity_description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state."""

        try:
            state = self.entity_description.value_fn(self.data)
        except KeyError, ValueError:
            return None

        return state
