"""Sensor for Suez Water Consumption data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from pysuez.const import ATTRIBUTION

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CURRENCY_EURO, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COUNTER_ID, DOMAIN
from .coordinator import SuezWaterConfigEntry, SuezWaterCoordinator, SuezWaterData


@dataclass(frozen=True, kw_only=True)
class SuezWaterSensorEntityDescription(SensorEntityDescription):
    """Describes Suez water sensor entity."""

    value_fn: Callable[[SuezWaterData], float | str | None]
    attr_fn: Callable[[SuezWaterData], dict[str, Any] | None] = lambda _: None


SENSORS: tuple[SuezWaterSensorEntityDescription, ...] = (
    SuezWaterSensorEntityDescription(
        key="water_usage_yesterday",
        translation_key="water_usage_yesterday",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        value_fn=lambda suez_data: suez_data.aggregated_value,
        attr_fn=lambda suez_data: asdict(suez_data.aggregated_attr),
    ),
    SuezWaterSensorEntityDescription(
        key="water_price",
        translation_key="water_price",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda suez_data: suez_data.price,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuezWaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Suez Water sensor from a config entry."""
    coordinator = entry.runtime_data
    counter_id = entry.data[CONF_COUNTER_ID]

    async_add_entities(
        SuezWaterSensor(coordinator, counter_id, description) for description in SENSORS
    )


class SuezWaterSensor(CoordinatorEntity[SuezWaterCoordinator], SensorEntity):
    """Representation of a Suez water sensor."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    entity_description: SuezWaterSensorEntityDescription

    def __init__(
        self,
        coordinator: SuezWaterCoordinator,
        counter_id: int,
        entity_description: SuezWaterSensorEntityDescription,
    ) -> None:
        """Initialize the suez water sensor entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{counter_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(counter_id))},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Suez",
        )
        self.entity_description = entity_description

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state of the sensor."""
        return self.entity_description.attr_fn(self.coordinator.data)
