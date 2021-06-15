"""Support for WLED sensors."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import DEVICE_CLASS_CURRENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_BYTES,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import ATTR_LED_COUNT, ATTR_MAX_POWER, CURRENT_MA, DOMAIN
from .coordinator import WLEDDataUpdateCoordinator
from .models import WLEDEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED sensor based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        WLEDEstimatedCurrentSensor(coordinator),
        WLEDUptimeSensor(coordinator),
        WLEDFreeHeapSensor(coordinator),
        WLEDWifiBSSIDSensor(coordinator),
        WLEDWifiChannelSensor(coordinator),
        WLEDWifiRSSISensor(coordinator),
        WLEDWifiSignalSensor(coordinator),
    ]

    async_add_entities(sensors)


class WLEDEstimatedCurrentSensor(WLEDEntity, SensorEntity):
    """Defines a WLED estimated current sensor."""

    _attr_icon = "mdi:power"
    _attr_unit_of_measurement = CURRENT_MA
    _attr_device_class = DEVICE_CLASS_CURRENT

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED estimated current sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_name = f"{coordinator.data.info.name} Estimated Current"
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_estimated_current"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        return {
            ATTR_LED_COUNT: self.coordinator.data.info.leds.count,
            ATTR_MAX_POWER: self.coordinator.data.info.leds.max_power,
        }

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.info.leds.power


class WLEDUptimeSensor(WLEDEntity, SensorEntity):
    """Defines a WLED uptime sensor."""

    _attr_device_class = DEVICE_CLASS_TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED uptime sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_name = f"{coordinator.data.info.name} Uptime"
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_uptime"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        uptime = utcnow() - timedelta(seconds=self.coordinator.data.info.uptime)
        return uptime.replace(microsecond=0).isoformat()


class WLEDFreeHeapSensor(WLEDEntity, SensorEntity):
    """Defines a WLED free heap sensor."""

    _attr_icon = "mdi:memory"
    _attr_entity_registry_enabled_default = False
    _attr_unit_of_measurement = DATA_BYTES

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED free heap sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_name = f"{coordinator.data.info.name} Free Memory"
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_free_heap"

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.info.free_heap


class WLEDWifiSignalSensor(WLEDEntity, SensorEntity):
    """Defines a WLED Wi-Fi signal sensor."""

    _attr_icon = "mdi:wifi"
    _attr_unit_of_measurement = PERCENTAGE
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED Wi-Fi signal sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_name = f"{coordinator.data.info.name} Wi-Fi Signal"
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_wifi_signal"

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data.info.wifi:
            return None
        return self.coordinator.data.info.wifi.signal


class WLEDWifiRSSISensor(WLEDEntity, SensorEntity):
    """Defines a WLED Wi-Fi RSSI sensor."""

    _attr_device_class = DEVICE_CLASS_SIGNAL_STRENGTH
    _attr_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED Wi-Fi RSSI sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_name = f"{coordinator.data.info.name} Wi-Fi RSSI"
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_wifi_rssi"

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data.info.wifi:
            return None
        return self.coordinator.data.info.wifi.rssi


class WLEDWifiChannelSensor(WLEDEntity, SensorEntity):
    """Defines a WLED Wi-Fi Channel sensor."""

    _attr_icon = "mdi:wifi"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED Wi-Fi Channel sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_name = f"{coordinator.data.info.name} Wi-Fi Channel"
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_wifi_channel"

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data.info.wifi:
            return None
        return self.coordinator.data.info.wifi.channel


class WLEDWifiBSSIDSensor(WLEDEntity, SensorEntity):
    """Defines a WLED Wi-Fi BSSID sensor."""

    _attr_icon = "mdi:wifi"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED Wi-Fi BSSID sensor."""
        super().__init__(coordinator=coordinator)
        self._attr_name = f"{coordinator.data.info.name} Wi-Fi BSSID"
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_wifi_bssid"

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data.info.wifi:
            return None
        return self.coordinator.data.info.wifi.bssid
