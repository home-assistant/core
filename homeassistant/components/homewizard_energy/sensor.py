"""Creates Homewizard Energy sensor entities."""
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

from .const import (
    ATTR_ACTIVE_POWER_L1_W,
    ATTR_ACTIVE_POWER_L2_W,
    ATTR_ACTIVE_POWER_L3_W,
    ATTR_ACTIVE_POWER_W,
    ATTR_GAS_TIMESTAMP,
    ATTR_METER_MODEL,
    ATTR_SMR_VERSION,
    ATTR_TOTAL_ENERGY_EXPORT_T1_KWH,
    ATTR_TOTAL_ENERGY_EXPORT_T2_KWH,
    ATTR_TOTAL_ENERGY_IMPORT_T1_KWH,
    ATTR_TOTAL_ENERGY_IMPORT_T2_KWH,
    ATTR_TOTAL_GAS_M3,
    ATTR_WIFI_SSID,
    ATTR_WIFI_STRENGTH,
    CONF_DATA,
    CONF_DEVICE,
    COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SENSORS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key=ATTR_SMR_VERSION,
        name="SMR Version",
        icon="mdi:counter",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ATTR_METER_MODEL,
        name="Model",
        icon="mdi:gauge",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ATTR_WIFI_SSID,
        name="Wifi SSID",
        icon="mdi:wifi",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ATTR_WIFI_STRENGTH,
        name="Wifi Strength",
        icon="mdi:wifi",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_IMPORT_T1_KWH,
        name="Total Power Import T1",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_IMPORT_T2_KWH,
        name="Total Power Import T2",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_EXPORT_T1_KWH,
        name="Total Power Export T1",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_EXPORT_T2_KWH,
        name="Total Power Export T2",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_ACTIVE_POWER_W,
        name="Active Power",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_ACTIVE_POWER_L1_W,
        name="Active Power L1",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_ACTIVE_POWER_L2_W,
        name="Active Power L2",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_ACTIVE_POWER_L3_W,
        name="Active Power L3",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_GAS_M3,
        name="Total Gas",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=DEVICE_CLASS_GAS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_GAS_TIMESTAMP,
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
    """Representation of a HomeWizard Energy Sensor."""

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
            ATTR_TOTAL_ENERGY_EXPORT_T1_KWH,
            ATTR_TOTAL_ENERGY_EXPORT_T2_KWH,
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
