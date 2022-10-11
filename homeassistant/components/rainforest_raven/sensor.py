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
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_KILO_WATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .data import RAVEnDataCoordinator


@dataclass
class RAVEnSensorEntityDescription(SensorEntityDescription):
    """A class that describes RAVEn sensor entities."""

    message_key: str | None = None
    attribute_keys: dict[str, str] | None = None


SENSORS = (
    RAVEnSensorEntityDescription(
        message_key="CurrentSummationDelivered",
        key="summation_delivered",
        name="Total Meter Energy Delivered",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RAVEnSensorEntityDescription(
        message_key="CurrentSummationDelivered",
        key="summation_received",
        name="Total Meter Energy Received",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RAVEnSensorEntityDescription(
        message_key="InstantaneousDemand",
        key="demand",
        name="Meter Power Demand",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


DIAGNOSTICS = (
    RAVEnSensorEntityDescription(
        message_key="NetworkInfo",
        key="link_strength",
        name="Link Strength",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        attribute_keys={
            "Channel": "channel",
        },
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
                        key="price",
                        name="Meter Price",
                        native_unit_of_measurement=f"{meter_data['PriceCluster']['currency'].value}/{ENERGY_KILO_WATT_HOUR}",
                        device_class=SensorDeviceClass.MONETARY,
                        state_class=SensorStateClass.MEASUREMENT,
                        attribute_keys={
                            "Tier": "tier",
                            "Rate": "rate_label",
                        },
                    ),
                    meter_mac_addr,
                )
            )

    async_add_entities(entities)


class RAVEnSensor(CoordinatorEntity, SensorEntity):
    """Rainforest RAVEn Sensor."""

    entity_description: RAVEnSensorEntityDescription

    def __init__(
        self,
        coordinator: RAVEnDataCoordinator,
        entity_description: RAVEnSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

    @property
    def _data(self) -> Any:
        """Return the raw sensor data from the source."""
        return self.coordinator.data.get(self.entity_description.message_key, {})

    @property
    def _source_mac_address(self) -> Any:
        """Return the MAC address of the data source."""
        return self.coordinator.device_mac_address

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        if self.entity_description.attribute_keys:
            return {
                name: self._data.get(key)
                for name, key in self.entity_description.attribute_keys.items()
            }
        return None

    @property
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return f"{self._source_mac_address}.{self.entity_description.message_key}.{self.entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return native value of the sensor."""
        return str(self._data.get(self.entity_description.key))

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_mac_address)},
            manufacturer=self.coordinator.device_manufacturer,
            model=self.coordinator.device_model,
            name=self.coordinator.device_name,
            sw_version=self.coordinator.device_fw_version,
            hw_version=self.coordinator.device_hw_version,
        )


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

    @property
    def _data(self) -> Any:
        """Return the raw sensor data from the source."""
        return (
            self.coordinator.data.get("Meters", {})
            .get(self._meter_mac_addr, {})
            .get(self.entity_description.message_key, {})
        )

    @property
    def _source_mac_address(self) -> str:
        """Return the MAC address of the data source."""
        return self._meter_mac_addr
