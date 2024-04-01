"""Sensor entity for a Rainforest RAVEn device."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_MAC,
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RAVEnDataCoordinator


@dataclass(frozen=True, kw_only=True)
class RAVEnSensorEntityDescription(SensorEntityDescription):
    """A class that describes RAVEn sensor entities."""

    message_key: str
    attribute_keys: list[str] | None = None


SENSORS = (
    RAVEnSensorEntityDescription(
        message_key="CurrentSummationDelivered",
        translation_key="total_energy_delivered",
        key="summation_delivered",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RAVEnSensorEntityDescription(
        message_key="CurrentSummationDelivered",
        translation_key="total_energy_received",
        key="summation_received",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RAVEnSensorEntityDescription(
        message_key="InstantaneousDemand",
        translation_key="power_demand",
        key="demand",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


DIAGNOSTICS = (
    RAVEnSensorEntityDescription(
        message_key="NetworkInfo",
        translation_key="signal_strength",
        key="link_strength",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        attribute_keys=[
            "channel",
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[RAVEnSensor] = [
        RAVEnSensor(coordinator, description) for description in DIAGNOSTICS
    ]

    for meter_mac_addr in entry.data[CONF_MAC]:
        entities.extend(
            RAVEnMeterSensor(coordinator, description, meter_mac_addr)
            for description in SENSORS
        )

        meter_data = coordinator.data.get("Meters", {}).get(meter_mac_addr) or {}
        if meter_data.get("PriceCluster", {}).get("currency"):
            entities.append(
                RAVEnMeterSensor(
                    coordinator,
                    RAVEnSensorEntityDescription(
                        message_key="PriceCluster",
                        translation_key="meter_price",
                        key="price",
                        native_unit_of_measurement=f"{meter_data['PriceCluster']['currency'].value}/{UnitOfEnergy.KILO_WATT_HOUR}",
                        state_class=SensorStateClass.MEASUREMENT,
                        attribute_keys=[
                            "tier",
                            "rate_label",
                        ],
                    ),
                    meter_mac_addr,
                )
            )

    async_add_entities(entities)


class RAVEnSensor(CoordinatorEntity[RAVEnDataCoordinator], SensorEntity):
    """Rainforest RAVEn Sensor."""

    _attr_has_entity_name = True
    entity_description: RAVEnSensorEntityDescription

    def __init__(
        self,
        coordinator: RAVEnDataCoordinator,
        entity_description: RAVEnSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{self.coordinator.device_mac_address}"
            f".{self.entity_description.message_key}.{self.entity_description.key}"
        )

    @property
    def _data(self) -> Any:
        """Return the raw sensor data from the source."""
        return self.coordinator.data.get(self.entity_description.message_key, {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        if self.entity_description.attribute_keys:
            return {
                key: self._data.get(key)
                for key in self.entity_description.attribute_keys
            }
        return None

    @property
    def native_value(self) -> StateType:
        """Return native value of the sensor."""
        return str(self._data.get(self.entity_description.key))


class RAVEnMeterSensor(RAVEnSensor):
    """Rainforest RAVEn Meter Sensor."""

    def __init__(
        self,
        coordinator: RAVEnDataCoordinator,
        entity_description: RAVEnSensorEntityDescription,
        meter_mac_addr: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)
        self._meter_mac_addr = meter_mac_addr
        self._attr_unique_id = (
            f"{self._meter_mac_addr}"
            f".{self.entity_description.message_key}.{self.entity_description.key}"
        )

    @property
    def _data(self) -> Any:
        """Return the raw sensor data from the source."""
        return (
            self.coordinator.data.get("Meters", {})
            .get(self._meter_mac_addr, {})
            .get(self.entity_description.message_key, {})
        )
