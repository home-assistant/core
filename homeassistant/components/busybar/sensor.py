"""Battery, power and Wi-Fi sensors for BUSY Bar."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from busylib.types import PowerState, WifiState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import BusyConfigEntry, BusyData
from .entity import BusyEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BusySensorEntityDescription(SensorEntityDescription):
    """Describe a BUSY Bar sensor."""

    value_fn: Callable[[BusyData], int | str | datetime | None]


SENSORS = (
    BusySensorEntityDescription(
        key="battery",
        value_fn=lambda d: d.power.battery_charge,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BusySensorEntityDescription(
        key="wifi_signal",
        value_fn=lambda d: d.wifi.rssi if d.wifi.state == WifiState.CONNECTED else None,
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BusySensorEntityDescription(
        key="charging_state",
        value_fn=lambda d: d.power.state,
        translation_key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in PowerState],
    ),
    BusySensorEntityDescription(
        key="battery_voltage",
        value_fn=lambda d: d.power.battery_voltage,
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BusySensorEntityDescription(
        key="battery_current",
        value_fn=lambda d: d.power.battery_current,
        translation_key="battery_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BusySensorEntityDescription(
        key="usb_voltage",
        value_fn=lambda d: d.power.usb_voltage,
        translation_key="usb_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BusySensorEntityDescription(
        key="uptime",
        value_fn=lambda d: (
            dt_util.utc_from_timestamp(d.status.system.boot_time)
            if d.status.system and d.status.system.boot_time is not None
            else None
        ),
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BusySensorEntityDescription(
        key="wifi_ssid",
        value_fn=lambda d: d.wifi.ssid,
        translation_key="wifi_ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BusySensorEntityDescription(
        key="wifi_channel",
        value_fn=lambda d: d.wifi.channel,
        translation_key="wifi_channel",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BusySensorEntityDescription(
        key="ip_address",
        value_fn=lambda d: d.wifi.ip_config.address if d.wifi.ip_config else None,
        translation_key="ip_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BusyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BUSY Bar sensors."""
    async_add_entities(
        BusySensor(entry.runtime_data, description) for description in SENSORS
    )


class BusySensor(BusyEntity, SensorEntity):
    """One value from the bar's last successful poll."""

    entity_description: BusySensorEntityDescription

    @property
    @override
    def native_value(self) -> int | str | datetime | None:
        """Return the reading from the last poll."""
        return self.entity_description.value_fn(self.coordinator.data)
