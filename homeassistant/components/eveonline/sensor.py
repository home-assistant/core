"""Sensor platform for the Eve Online integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EveOnlineConfigEntry, EveOnlineCoordinator, EveOnlineData
from .entity import EveOnlineCharacterEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EveOnlineSensorDescription(SensorEntityDescription):
    """Describe an Eve Online sensor."""

    value_fn: Callable[[EveOnlineData], str | float | None]


SENSORS: tuple[EveOnlineSensorDescription, ...] = (
    EveOnlineSensorDescription(
        key="online",
        translation_key="online",
        device_class=SensorDeviceClass.ENUM,
        options=["online", "offline"],
        value_fn=lambda data: "online" if data.online else "offline",
    ),
    EveOnlineSensorDescription(
        key="wallet_balance",
        translation_key="wallet_balance",
        native_unit_of_measurement="ISK",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: (
            data.wallet_balance.balance if data.wallet_balance else None
        ),
    ),
    EveOnlineSensorDescription(
        key="location",
        translation_key="location",
        value_fn=lambda data: data.solar_system_name,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EveOnlineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eve Online sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        EveOnlineCharacterSensor(coordinator, description) for description in SENSORS
    )


class EveOnlineCharacterSensor(EveOnlineCharacterEntity, SensorEntity):
    """Representation of an Eve Online sensor."""

    entity_description: EveOnlineSensorDescription

    def __init__(
        self,
        coordinator: EveOnlineCoordinator,
        description: EveOnlineSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
