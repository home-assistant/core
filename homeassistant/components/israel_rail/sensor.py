"""Support for israel rail."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant import config_entries, core
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_CONNECTIONS_COUNT
from .coordinator import DataConnection, IsraelRailDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=90)


@dataclass(kw_only=True, frozen=True)
class IsraelRailSensorEntityDescription(SensorEntityDescription):
    """Describes israel rail sensor entity."""

    value_fn: Callable[[DataConnection], StateType | datetime]

    index: int = 0
    has_legacy_attributes: bool = False


SENSORS: tuple[IsraelRailSensorEntityDescription, ...] = (
    *[
        IsraelRailSensorEntityDescription(
            key=f"departure{i or ''}",
            translation_key=f"departure{i}",
            device_class=SensorDeviceClass.TIMESTAMP,
            has_legacy_attributes=i == 0,
            value_fn=lambda data_connection: data_connection["departure"],
            index=i,
        )
        for i in range(SENSOR_CONNECTIONS_COUNT)
    ],
    IsraelRailSensorEntityDescription(
        key="duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data_connection: data_connection["duration"],
    ),
    IsraelRailSensorEntityDescription(
        key="transfers",
        translation_key="transfers",
        value_fn=lambda data_connection: data_connection["transfers"],
    ),
    IsraelRailSensorEntityDescription(
        key="platform",
        translation_key="platform",
        value_fn=lambda data_connection: data_connection["platform"],
    ),
)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    unique_id = config_entry.unique_id

    if TYPE_CHECKING:
        assert unique_id

    async_add_entities(
        IsraelRailSensor(coordinator, description, unique_id) for description in SENSORS
    )


class IsraelRailSensor(
    CoordinatorEntity[IsraelRailDataUpdateCoordinator], SensorEntity
):
    """Implementation of a Israel Rail sensor."""

    entity_description: IsraelRailSensorEntityDescription
    _attr_attribution = "Data provided by israel rail."
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
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data[self.entity_description.index]
        )

    async def async_added_to_hass(self) -> None:
        """Prepare the extra attributes at start."""
        if self.entity_description.has_legacy_attributes:
            self._async_update_attrs()
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle the state update and prepare the extra state attributes."""
        if self.entity_description.has_legacy_attributes:
            self._async_update_attrs()
        return super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the extra state attributes based on the coordinator data."""
        if self.entity_description.has_legacy_attributes:
            self._attr_extra_state_attributes = {
                key: value
                for key, value in self.coordinator.data[
                    self.entity_description.index
                ].items()
                if key not in {"departure"}
            }
