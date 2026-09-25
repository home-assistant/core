"""sensor platform for Netis Router.

Exposes router telemetry as HA sensor entities:

System & Traffic:
  - Uptime (duration, seconds)
  - Download / Upload speed (data_rate, B/s)
  - Download / Upload total (data_size, bytes, total_increasing)
  - Online device count

LTE / 4G (optional, only on LTE-capable models):
  - RSRP, RSSI (signal_strength, dBm)
  - RSRQ (dB)
  - Network mode (e.g. "LTE")
  - Operator name (e.g. "CHN-CT")
  - LTE IP address

Diagnostic:
  - Firmware version
  - IMEI

All sensors read from the coordinator's cached :class:`NetisData` snapshot
updated on each poll cycle.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetisCoordinator
from .entity import NetisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Netis sensors."""
    coordinator: NetisCoordinator = entry.runtime_data
    entities: list[NetisSensorEntity] = [
        # System / traffic
        _Sensor(
            coordinator,
            key="uptime",
            name="Uptime",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit=UnitOfTime.SECONDS,
            value=lambda d: d.uptime,
        ),
        _Sensor(
            coordinator,
            key="wan_download_speed",
            name="Download speed",
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit=UnitOfDataRate.BYTES_PER_SECOND,
            value=lambda d: d.wan_in_speed,
            icon="mdi:download-network",
        ),
        _Sensor(
            coordinator,
            key="wan_upload_speed",
            name="Upload speed",
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit=UnitOfDataRate.BYTES_PER_SECOND,
            value=lambda d: d.wan_out_speed,
            icon="mdi:upload-network",
        ),
        _Sensor(
            coordinator,
            key="wan_download_total",
            name="Download total",
            device_class=SensorDeviceClass.DATA_SIZE,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit=UnitOfInformation.BYTES,
            value=lambda d: d.wan_in_bytes,
            icon="mdi:download",
        ),
        _Sensor(
            coordinator,
            key="wan_upload_total",
            name="Upload total",
            device_class=SensorDeviceClass.DATA_SIZE,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit=UnitOfInformation.BYTES,
            value=lambda d: d.wan_out_bytes,
            icon="mdi:upload",
        ),
        _Sensor(
            coordinator,
            key="online_devices",
            name="Online devices",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit="devices",
            value=lambda d: sum(1 for dev in d.devices if dev.online),
            icon="mdi:devices",
        ),
        # LTE / 4G
        _Sensor(
            coordinator,
            key="lte_rsrp",
            name="LTE RSRP",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit=SIGNAL_STRENGTH_DECIBELS,
            value=lambda d: d.lte_rsrp,
            icon="mdi:signal",
        ),
        _Sensor(
            coordinator,
            key="lte_rsrq",
            name="LTE RSRQ",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit=SIGNAL_STRENGTH_DECIBELS,
            value=lambda d: d.lte_rsrq,
            icon="mdi:signal-variant",
        ),
        _Sensor(
            coordinator,
            key="lte_rssi",
            name="LTE RSSI",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit=SIGNAL_STRENGTH_DECIBELS,
            value=lambda d: d.lte_rssi,
            icon="mdi:signal-hangup",
        ),
        _Sensor(
            coordinator,
            key="lte_mode",
            name="LTE network mode",
            value=lambda d: d.lte_mode,
            icon="mdi:access-point-network",
        ),
        _Sensor(
            coordinator,
            key="lte_isp",
            name="LTE operator",
            value=lambda d: d.lte_isp,
            icon="mdi:cellphone-information",
        ),
        _Sensor(
            coordinator,
            key="lte_ip",
            name="LTE IP address",
            value=lambda d: d.lte_ip,
            icon="mdi:ip",
        ),
        # Diagnostic
        _Sensor(
            coordinator,
            key="firmware",
            name="Firmware",
            entity_category=EntityCategory.DIAGNOSTIC,
            value=lambda d: d.firmware,
            icon="mdi:chip",
        ),
        _Sensor(
            coordinator,
            key="imei",
            name="IMEI",
            entity_category=EntityCategory.DIAGNOSTIC,
            value=lambda d: d.lte_imei,
            icon="mdi:barcode",
        ),
    ]
    async_add_entities(entities)


class NetisSensorEntity(NetisEntity, SensorEntity):
    """Common router sensor."""


class _Sensor(NetisSensorEntity):
    """Configurable sensor bound to a snapshot field via a callable."""

    def __init__(
        self,
        coordinator: NetisCoordinator,
        *,
        key: str,
        name: str,
        value,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        native_unit: str | None = None,
        entity_category: EntityCategory | None = None,
        icon: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{key}"
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = native_unit
        self._attr_entity_category = entity_category
        self._attr_icon = icon
        self._getter = value

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self._getter(self.coordinator.data)
