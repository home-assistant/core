"""Support for israel rail."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DEPARTURES_COUNT, DOMAIN
from .coordinator import (
    DataConnection,
    IsraelRailConfigEntry,
    IsraelRailDataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, frozen=True)
class IsraelRailSensorEntityDescription(SensorEntityDescription):
    """Describes israel rail sensor entity."""

    value_fn: Callable[[DataConnection], StateType | datetime]

    index: int = 0


DEPARTURE_SENSORS: tuple[IsraelRailSensorEntityDescription, ...] = (
    *[
        IsraelRailSensorEntityDescription(
            key=f"departure{i or ''}",
            translation_key=f"departure{i}",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=lambda data_connection: data_connection.departure,
            index=i,
        )
        for i in range(DEPARTURES_COUNT)
    ],
)

SENSORS: tuple[IsraelRailSensorEntityDescription, ...] = (
    IsraelRailSensorEntityDescription(
        key="platform",
        translation_key="platform",
        value_fn=lambda data_connection: data_connection.platform,
    ),
    IsraelRailSensorEntityDescription(
        key="trains",
        translation_key="trains",
        value_fn=lambda data_connection: data_connection.trains,
    ),
    IsraelRailSensorEntityDescription(
        key="train_number",
        translation_key="train_number",
        value_fn=lambda data_connection: data_connection.train_number,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: IsraelRailConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    coordinator = config_entry.runtime_data

    unique_id = config_entry.unique_id

    if TYPE_CHECKING:
        assert unique_id

    async_add_entities(
        IsraelRailEntitySensor(coordinator, description, unique_id)
        for description in (*DEPARTURE_SENSORS, *SENSORS)
    )


class IsraelRailEntitySensor(
    CoordinatorEntity[IsraelRailDataUpdateCoordinator], SensorEntity
):
    """Define a Israel Rail sensor."""

    entity_description: IsraelRailSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IsraelRailDataUpdateCoordinator,
        entity_description: IsraelRailSensorEntityDescription,
        unique_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data[self.entity_description.index]
        )
