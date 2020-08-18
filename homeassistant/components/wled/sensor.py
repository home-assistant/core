"""Support for WLED sensors."""
from datetime import timedelta
import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.sensor import DEVICE_CLASS_CURRENT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_BYTES,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TIMESTAMP,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.dt import utcnow

from . import WLEDDataUpdateCoordinator, WLEDDeviceEntity
from .const import ATTR_LED_COUNT, ATTR_MAX_POWER, CURRENT_MA, DOMAIN, SIGNAL_DBM

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up WLED sensor based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        WLEDEstimatedCurrentSensor(entry.entry_id, coordinator),
        WLEDUptimeSensor(entry.entry_id, coordinator),
        WLEDFreeHeapSensor(entry.entry_id, coordinator),
        WLEDWifiBSSIDSensor(entry.entry_id, coordinator),
        WLEDWifiChannelSensor(entry.entry_id, coordinator),
        WLEDWifiRSSISensor(entry.entry_id, coordinator),
        WLEDWifiSignalSensor(entry.entry_id, coordinator),
    ]

    async_add_entities(sensors, True)


class WLEDSensor(WLEDDeviceEntity):
    """Defines a WLED sensor."""

    def __init__(
        self,
        *,
        coordinator: WLEDDataUpdateCoordinator,
        enabled_default: bool = True,
        entry_id: str,
        icon: str,
        key: str,
        name: str,
        unit_of_measurement: Optional[str] = None,
    ) -> None:
        """Initialize WLED sensor."""
        self._unit_of_measurement = unit_of_measurement
        self._key = key

        super().__init__(
            entry_id=entry_id,
            coordinator=coordinator,
            name=name,
            icon=icon,
            enabled_default=enabled_default,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.coordinator.data.info.mac_address}_{self._key}"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class WLEDEstimatedCurrentSensor(WLEDSensor):
    """Defines a WLED estimated current sensor."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED estimated current sensor."""
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            icon="mdi:power",
            key="estimated_current",
            name=f"{coordinator.data.info.name} Estimated Current",
            unit_of_measurement=CURRENT_MA,
        )

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        return {
            ATTR_LED_COUNT: self.coordinator.data.info.leds.count,
            ATTR_MAX_POWER: self.coordinator.data.info.leds.max_power,
        }

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.info.leds.power

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this sensor."""
        return DEVICE_CLASS_CURRENT


class WLEDUptimeSensor(WLEDSensor):
    """Defines a WLED uptime sensor."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED uptime sensor."""
        super().__init__(
            coordinator=coordinator,
            enabled_default=False,
            entry_id=entry_id,
            icon="mdi:clock-outline",
            key="uptime",
            name=f"{coordinator.data.info.name} Uptime",
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        uptime = utcnow() - timedelta(seconds=self.coordinator.data.info.uptime)
        return uptime.replace(microsecond=0).isoformat()

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this sensor."""
        return DEVICE_CLASS_TIMESTAMP


class WLEDFreeHeapSensor(WLEDSensor):
    """Defines a WLED free heap sensor."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED free heap sensor."""
        super().__init__(
            coordinator=coordinator,
            enabled_default=False,
            entry_id=entry_id,
            icon="mdi:memory",
            key="free_heap",
            name=f"{coordinator.data.info.name} Free Memory",
            unit_of_measurement=DATA_BYTES,
        )

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.info.free_heap


class WLEDWifiSignalSensor(WLEDSensor):
    """Defines a WLED Wi-Fi signal sensor."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED Wi-Fi signal sensor."""
        super().__init__(
            coordinator=coordinator,
            enabled_default=False,
            entry_id=entry_id,
            icon="mdi:wifi",
            key="wifi_signal",
            name=f"{coordinator.data.info.name} Wi-Fi Signal",
            unit_of_measurement=UNIT_PERCENTAGE,
        )

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.info.wifi.signal


class WLEDWifiRSSISensor(WLEDSensor):
    """Defines a WLED Wi-Fi RSSI sensor."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED Wi-Fi RSSI sensor."""
        super().__init__(
            coordinator=coordinator,
            enabled_default=False,
            entry_id=entry_id,
            icon="mdi:wifi",
            key="wifi_rssi",
            name=f"{coordinator.data.info.name} Wi-Fi RSSI",
            unit_of_measurement=SIGNAL_DBM,
        )

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.info.wifi.rssi

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this sensor."""
        return DEVICE_CLASS_SIGNAL_STRENGTH


class WLEDWifiChannelSensor(WLEDSensor):
    """Defines a WLED Wi-Fi Channel sensor."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED Wi-Fi Channel sensor."""
        super().__init__(
            coordinator=coordinator,
            enabled_default=False,
            entry_id=entry_id,
            icon="mdi:wifi",
            key="wifi_channel",
            name=f"{coordinator.data.info.name} Wi-Fi Channel",
        )

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.data.info.wifi.channel


class WLEDWifiBSSIDSensor(WLEDSensor):
    """Defines a WLED Wi-Fi BSSID sensor."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED Wi-Fi BSSID sensor."""
        super().__init__(
            coordinator=coordinator,
            enabled_default=False,
            entry_id=entry_id,
            icon="mdi:wifi",
            key="wifi_bssid",
            name=f"{coordinator.data.info.name} Wi-Fi BSSID",
        )

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.info.wifi.bssid
