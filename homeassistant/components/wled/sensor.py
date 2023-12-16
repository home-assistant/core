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
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .coordinator import WLEDDataUpdateCoordinator
from .models import WLEDEntity


@dataclass(kw_only=True)
class WLEDSensorEntityDescription(SensorEntityDescription):
    """Describes WLED sensor entity."""

    exists_fn: Callable[[WLEDDevice], bool] = lambda _: True
    value_fn: Callable[[WLEDDevice], datetime | StateType]


SENSORS: tuple[WLEDSensorEntityDescription, ...] = (
    WLEDSensorEntityDescription(
        key="estimated_current",
        translation_key="estimated_current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.leds.power,
        exists_fn=lambda device: bool(device.info.leds.max_power),
    ),
    WLEDSensorEntityDescription(
        key="info_leds_count",
        translation_key="info_leds_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.leds.count,
    ),
    WLEDSensorEntityDescription(
        key="info_leds_max_power",
        translation_key="info_leds_max_power",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.CURRENT,
        value_fn=lambda device: device.info.leds.max_power,
        exists_fn=lambda device: bool(device.info.leds.max_power),
    ),
    WLEDSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: (utcnow() - timedelta(seconds=device.info.uptime)),
    ),
    WLEDSensorEntityDescription(
        key="free_heap",
        translation_key="free_heap",
        icon="mdi:memory",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.free_heap,
    ),
    WLEDSensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        icon="mdi:wifi",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.signal if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.rssi if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_channel",
        translation_key="wifi_channel",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.channel if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="wifi_bssid",
        translation_key="wifi_bssid",
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.info.wifi.bssid if device.info.wifi else None,
    ),
    WLEDSensorEntityDescription(
        key="ip",
        translation_key="ip",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.info.ip,
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
        WLEDSensorEntity(coordinator, description)
        for description in SENSORS
        if description.exists_fn(coordinator.data)
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
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_{description.key}"

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
