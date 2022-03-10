"""Creates Homewizard sensor entities."""
from __future__ import annotations

import logging
from typing import Final, cast

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SERVICE_DATA, SERVICE_DEVICE, DeviceResponseEntry
from .coordinator import HWEnergyDeviceUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSORS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key="smr_version",
        name="DSMR Version",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="meter_model",
        name="Smart Meter Model",
        icon="mdi:gauge",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="wifi_ssid",
        name="Wifi SSID",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="wifi_strength",
        name="Wifi Strength",
        icon="mdi:wifi",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="total_power_import_t1_kwh",
        name="Total Power Import T1",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="total_power_import_t2_kwh",
        name="Total Power Import T2",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="total_power_export_t1_kwh",
        name="Total Power Export T1",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="total_power_export_t2_kwh",
        name="Total Power Export T2",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="active_power_w",
        name="Active Power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="active_power_l1_w",
        name="Active Power L1",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="active_power_l2_w",
        name="Active Power L2",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="active_power_l3_w",
        name="Active Power L3",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_gas_m3",
        name="Total Gas",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=DEVICE_CLASS_GAS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize sensors."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    if coordinator.api.data is not None:
        for description in SENSORS:
            if getattr(coordinator.data[SERVICE_DATA], description.key) is not None:
                entities.append(HWEnergySensor(coordinator, entry, description))
    async_add_entities(entities)


class HWEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a HomeWizard Sensor."""

    coordinator: HWEnergyDeviceUpdateCoordinator

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Sensor Domain."""

        super().__init__(coordinator)
        self.entity_description = description
        self.entry = entry

        # Config attributes.
        self._attr_name = f"{entry.title} {description.name}"
        self.data_type = description.key
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

        # Special case for export, not everyone has solarpanels
        # The chance that 'export' is non-zero when you have solar panels is nil
        if self.data_type in [
            "total_power_export_t1_kwh",
            "total_power_export_t2_kwh",
        ]:
            if self.native_value == 0:
                self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "name": self.entry.title,
            "manufacturer": "HomeWizard",
            "sw_version": self.data[SERVICE_DEVICE].firmware_version,
            "model": self.data[SERVICE_DEVICE].product_type,
            "identifiers": {(DOMAIN, self.data[SERVICE_DEVICE].serial)},
        }

    @property
    def data(self) -> DeviceResponseEntry:
        """Return data object from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def native_value(self) -> StateType:
        """Return state of meter."""
        return cast(StateType, getattr(self.data[SERVICE_DATA], self.data_type))

    @property
    def available(self) -> bool:
        """Return availability of meter."""
        return super().available and self.native_value is not None
