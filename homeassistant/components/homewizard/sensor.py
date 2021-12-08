"""Creates Homewizard sensor entities."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TIMESTAMP,
    ENERGY_KILO_WATT_HOUR,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
    POWER_WATT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DATA, CONF_DEVICE, COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSORS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key="smr_version",
        name="SMR Version",
        icon="mdi:counter",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="meter_model",
        name="Model",
        icon="mdi:gauge",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="wifi_ssid",
        name="Wifi SSID",
        icon="mdi:wifi",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="wifi_strength",
        name="Wifi Strength",
        icon="mdi:wifi",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
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
    SensorEntityDescription(
        key="gas_timestamp",
        name="Gas Timestamp",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Initialize sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    entities = []
    for description in SENSORS:
        if description.key in coordinator.api.data.available_datapoints:
            entities.append(HWEnergySensor(coordinator, entry, description))
    async_add_entities(entities)


class HWEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a HomeWizard Sensor."""

    def __init__(self, coordinator, entry, description):
        """Initialize Sensor Domain."""

        super().__init__(coordinator)
        self.entity_description = description
        self.entry = entry

        # Config attributes.
        self._attr_name = f"{entry.title} {description.name}"
        self.data_type = description.key
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

        # Some values are given, but set to NULL (eg. gas_timestamp when no gas meter is connected)
        if self.data[CONF_DATA][self.data_type] is None:
            self.entity_description.entity_registry_enabled_default = False

        # Special case for export, not everyone has solarpanels
        # The change that 'export' is non-zero when you have solar panels is nil
        if self.data_type in [
            "total_power_export_t1_kwh",
            "total_power_export_t2_kwh",
        ]:
            if self.data[CONF_DATA][self.data_type] == 0:
                self.entity_description.entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "name": self.entry.title,
            "manufacturer": "HomeWizard",
            "sw_version": self.data[CONF_DEVICE].firmware_version,
            "model": self.data[CONF_DEVICE].product_type,
            "identifiers": {(DOMAIN, self.data[CONF_DEVICE].serial)},
        }

    @property
    def data(self):
        """Return data object from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def native_value(self):
        """Return state of meter."""
        return self.data[CONF_DATA][self.data_type]

    @property
    def available(self):
        """Return availability of meter."""
        return self.data_type in self.data[CONF_DATA]
