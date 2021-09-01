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
    CONF_ID,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TIMESTAMP,
    ENERGY_KILO_WATT_HOUR,
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
    ATTR_TOTAL_GAS_M3,
    ATTR_TOTAL_POWER_EXPORT_T1_KWH,
    ATTR_TOTAL_POWER_EXPORT_T2_KWH,
    ATTR_TOTAL_POWER_IMPORT_T1_KWH,
    ATTR_TOTAL_POWER_IMPORT_T2_KWH,
    ATTR_WIFI_SSID,
    ATTR_WIFI_STRENGTH,
    CONF_API,
    CONF_DATA,
    CONF_MODEL,
    CONF_SW_VERSION,
    COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SENSORS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key=ATTR_SMR_VERSION,
        name="SMR version",
        icon="mdi:wifi",
    ),
    SensorEntityDescription(
        key=ATTR_METER_MODEL,
        name="Model",
        icon="mdi:counter",
    ),
    SensorEntityDescription(
        key=ATTR_WIFI_SSID,
        name="Wifi SSID",
        icon="mdi:wifi",
    ),
    SensorEntityDescription(
        key=ATTR_WIFI_STRENGTH,
        name="Wifi Strength",
        icon="mdi:wifi",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_POWER_IMPORT_T1_KWH,
        name="Total power import T1",
        icon="mdi:home-import-outline",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_POWER_IMPORT_T2_KWH,
        name="Total power import T2",
        icon="mdi:home-import-outline",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_POWER_EXPORT_T1_KWH,
        name="Total power export T1",
        icon="mdi:home-export-outline",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_POWER_EXPORT_T2_KWH,
        name="Total power export T2",
        icon="mdi:home-export-outline",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_ACTIVE_POWER_W,
        name="Active power",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_ACTIVE_POWER_L1_W,
        name="Active power L1",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_ACTIVE_POWER_L2_W,
        name="Active power L2",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_ACTIVE_POWER_L3_W,
        name="Active power L3",
        icon="mdi:transmission-tower",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_GAS_M3,
        name="Total gas",
        icon="mdi:fire",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        device_class=DEVICE_CLASS_GAS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=ATTR_GAS_TIMESTAMP,
        name="Gas timestamp",
        icon="mdi:timeline-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    energy_api = hass.data[DOMAIN][entry.data["unique_id"]][CONF_API]
    coordinator = hass.data[DOMAIN][entry.data["unique_id"]][COORDINATOR]

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    if energy_api.data is not None:
        entities = []
        for description in SENSORS:
            if description.key in energy_api.data.available_datapoints:
                entities.append(HWEnergySensor(coordinator, entry.data, description))
        async_add_entities(entities, update_before_add=True)

        return True

    return False


class HWEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a HomeWizard Energy Sensor."""

    unique_id = None
    name = None

    def __init__(self, coordinator, entry_data, description):
        """Initialize Sensor Domain."""

        super().__init__(coordinator)
        self.entity_description = description
        self.coordinator = coordinator
        self.entry_data = entry_data

        # Config attributes.
        self.name = "{} {}".format(entry_data["custom_name"], description.name)
        self.data_type = description.key
        self.unique_id = "{}_{}".format(entry_data["unique_id"], description.key)

        # Some values are given, but set to NULL (eg. gas_timestamp when no gas meter is connected)
        if self.data[CONF_DATA][self.data_type] is None:
            self.entity_description.entity_registry_enabled_default = False

        # Special case for export, not everyone has solarpanels
        # The change that 'export' is non-zero when you have solar panels is nil
        if self.data_type in [
            ATTR_TOTAL_POWER_EXPORT_T1_KWH,
            ATTR_TOTAL_POWER_EXPORT_T2_KWH,
        ]:
            if self.data[CONF_DATA][self.data_type] == 0:
                self.entity_description.entity_registry_enabled_default = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return {
            "name": self.entry_data["custom_name"],
            "manufacturer": "HomeWizard",
            "sw_version": self.data[CONF_SW_VERSION],
            "model": self.data[CONF_MODEL],
            "identifiers": {(DOMAIN, self.data[CONF_ID])},
        }

    @property
    def data(self):
        """Return data object from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def icon(self):
        """Return the icon."""
        return self.entity_description.icon

    @property
    def state(self):
        """Return state of meter."""
        return self.data[CONF_DATA][self.data_type]

    @property
    def available(self):
        """Return availability of meter."""
        return self.data_type in self.data[CONF_DATA]
