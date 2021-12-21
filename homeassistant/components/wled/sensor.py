"""Support for WLED sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from wled import Device as WLEDDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_BYTES,
    ELECTRIC_CURRENT_MILLIAMPERE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .coordinator import WLEDDataUpdateCoordinator
from .models import WLEDEntity


@dataclass
class WLEDSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[WLEDDevice], datetime | StateType]


@dataclass
class WLEDSensorEntityDescription(
    SensorEntityDescription, WLEDSensorEntityDescriptionMixin
):
    """Describes WLED sensor entity."""


SENSORS: tuple[WLEDSensorEntityDescription, ...] = (
    WLEDSensorEntityDescription(
        key="estimated_current",
        name="Estimated Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.leds.power,
    ),
    WLEDSensorEntityDescription(
        key="info_leds_count",
        name="LED Count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.leds.count,
    ),
    WLEDSensorEntityDescription(
        key="info_leds_max_power",
        name="Max Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_MILLIAMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        value_fn=lambda device: device.info.leds.max_power,
    ),
    WLEDSensorEntityDescription(
        key="uptime",
        name="Uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (utcnow() - timedelta(seconds=device.info.uptime)),
    ),
    WLEDSensorEntityDescription(
        key="free_heap",
        name="Free Memory",
        icon="mdi:memory",
        native_unit_of_measurement=DATA_BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.free_heap,
    ),
    WLEDSensorEntityDescription(
        key="wifi_signal",
        name="Wi-Fi Signal",
        icon="mdi:wifi",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.signal if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_rssi",
        name="Wi-Fi RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.rssi if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_channel",
        name="Wi-Fi Channel",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.channel if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_bssid",
        name="Wi-Fi BSSID",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.bssid if device.info.wifi else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED sensor based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        WLEDSensorEntity(coordinator, description) for description in SENSORS
    )


class WLEDSensorEntity(WLEDEntity, SensorEntity):
    """Defines a WLED sensor entity."""

    entity_description: WLEDSensorEntityDescription

    def __init__(
        self,
        coordinator: WLEDDataUpdateCoordinator,
        description: WLEDSensorEntityDescription,
    ) -> None:
        """Initialize a WLED sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.data.info.name} {description.name}"
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_{description.key}"

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
