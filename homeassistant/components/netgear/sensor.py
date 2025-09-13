"""Support for Netgear routers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    KEY_COORDINATOR,
    KEY_COORDINATOR_LINK,
    KEY_COORDINATOR_TRAFFIC,
    KEY_COORDINATOR_UTIL,
    KEY_ROUTER,
)
from .entity import NetgearDeviceEntity, NetgearRouterCoordinatorEntity
from .router import NetgearRouter

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "type": SensorEntityDescription(
        key="type",
        translation_key="link_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "link_rate": SensorEntityDescription(
        key="link_rate",
        translation_key="link_rate",
        native_unit_of_measurement="Mbps",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "signal": SensorEntityDescription(
        key="signal",
        translation_key="signal_strength",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "ssid": SensorEntityDescription(
        key="ssid",
        translation_key="ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "conn_ap_mac": SensorEntityDescription(
        key="conn_ap_mac",
        translation_key="access_point_mac",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}


@dataclass(frozen=True, kw_only=True)
class NetgearSensorEntityDescription(SensorEntityDescription):
    """Class describing Netgear sensor entities."""

    value_fn: Callable
    index: int = 0


SENSOR_TRAFFIC_TYPES = [
    NetgearSensorEntityDescription(
        key="NewTodayUpload",
        translation_key="upload_today",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        value_fn=lambda data: data.upload_today,
    ),
    NetgearSensorEntityDescription(
        key="NewTodayDownload",
        translation_key="download_today",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        value_fn=lambda data: data.download_today,
    ),
    NetgearSensorEntityDescription(
        key="NewYesterdayUpload",
        translation_key="upload_yesterday",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        value_fn=lambda data: data.upload_yesterday,
    ),
    NetgearSensorEntityDescription(
        key="NewYesterdayDownload",
        translation_key="download_yesterday",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        value_fn=lambda data: data.download_yesterday,
    ),
    NetgearSensorEntityDescription(
        key="NewWeekUpload",
        translation_key="upload_week",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=0,
        value_fn=lambda data: data.total_upload_week,
    ),
    NetgearSensorEntityDescription(
        key="NewWeekUpload",
        translation_key="upload_week_average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=1,
        value_fn=lambda data: data.average_upload_week,
    ),
    NetgearSensorEntityDescription(
        key="NewWeekDownload",
        translation_key="download_week",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=0,
        value_fn=lambda data: data.total_download_week,
    ),
    NetgearSensorEntityDescription(
        key="NewWeekDownload",
        translation_key="download_week_average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=1,
        value_fn=lambda data: data.average_download_week,
    ),
    NetgearSensorEntityDescription(
        key="NewMonthUpload",
        translation_key="upload_month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=0,
        value_fn=lambda data: data.total_upload_month,
    ),
    NetgearSensorEntityDescription(
        key="NewMonthUpload",
        translation_key="upload_month_average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=1,
        value_fn=lambda data: data.average_upload_month,
    ),
    NetgearSensorEntityDescription(
        key="NewMonthDownload",
        translation_key="download_month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=0,
        value_fn=lambda data: data.total_download_month,
    ),
    NetgearSensorEntityDescription(
        key="NewMonthDownload",
        translation_key="download_month_average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=1,
        value_fn=lambda data: data.average_download_month,
    ),
    NetgearSensorEntityDescription(
        key="NewLastMonthUpload",
        translation_key="upload_last_month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=0,
        value_fn=lambda data: data.total_upload_last_month,
    ),
    NetgearSensorEntityDescription(
        key="NewLastMonthUpload",
        translation_key="upload_last_month_average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=1,
        value_fn=lambda data: data.average_upload_last_month,
    ),
    NetgearSensorEntityDescription(
        key="NewLastMonthDownload",
        translation_key="download_last_month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=0,
        value_fn=lambda data: data.total_download_last_month,
    ),
    NetgearSensorEntityDescription(
        key="NewLastMonthDownload",
        translation_key="download_last_month_average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        index=1,
        value_fn=lambda data: data.average_download_last_month,
    ),
]

# SENSOR_SPEED_TYPES = [
#     NetgearSensorEntityDescription(
#         key="NewOOKLAUplinkBandwidth",
#         translation_key="uplink_bandwidth",
#         entity_category=EntityCategory.DIAGNOSTIC,
#         native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
#         device_class=SensorDeviceClass.DATA_RATE,
#     ),
#     NetgearSensorEntityDescription(
#         key="NewOOKLADownlinkBandwidth",
#         translation_key="downlink_bandwidth",
#         entity_category=EntityCategory.DIAGNOSTIC,
#         native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
#         device_class=SensorDeviceClass.DATA_RATE,
#     ),
#     NetgearSensorEntityDescription(
#         key="AveragePing",
#         translation_key="average_ping",
#         entity_category=EntityCategory.DIAGNOSTIC,
#         native_unit_of_measurement=UnitOfTime.MILLISECONDS,
#     ),
# ]

SENSOR_UTILIZATION = [
    NetgearSensorEntityDescription(
        key="NewCPUUtilization",
        translation_key="cpu_utilization",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda system: system.cpu_usage,
    ),
    NetgearSensorEntityDescription(
        key="NewMemoryUtilization",
        translation_key="memory_utilization",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda system: system.memory_usage,
    ),
]

SENSOR_LINK_TYPES = [
    NetgearSensorEntityDescription(
        key="NewEthernetLinkStatus",
        translation_key="ethernet_link_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Netgear component."""
    router = hass.data[DOMAIN][entry.entry_id][KEY_ROUTER]
    coordinator = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR]
    coordinator_traffic = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR_TRAFFIC]
    # coordinator_speed = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR_SPEED]
    coordinator_utilization = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR_UTIL]
    coordinator_link = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR_LINK]

    async_add_entities(
        NetgearRouterSensorEntity(coordinator, router, description)
        for (coordinator, descriptions) in (
            (coordinator_traffic, SENSOR_TRAFFIC_TYPES),
            # (coordinator_speed, SENSOR_SPEED_TYPES),
            (coordinator_utilization, SENSOR_UTILIZATION),
            (coordinator_link, SENSOR_LINK_TYPES),
        )
        for description in descriptions
    )

    # Entities per network device
    tracked = set()
    sensors = ["type", "link_rate", "signal"]
    if router.method_version == 2:
        sensors.extend(["ssid", "conn_ap_mac"])

    @callback
    def new_device_callback() -> None:
        """Add new devices if needed."""
        if not coordinator.data:
            return

        new_entities: list[NetgearSensorEntity] = []

        for mac, device in router.devices.items():
            if mac in tracked:
                continue

            new_entities.extend(
                NetgearSensorEntity(coordinator, router, device, attribute)
                for attribute in sensors
            )
            tracked.add(mac)

        async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(new_device_callback))

    coordinator.data = True
    new_device_callback()


class NetgearSensorEntity(NetgearDeviceEntity, SensorEntity):
    """Representation of a device connected to a Netgear router."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: NetgearRouter,
        device: dict,
        attribute: str,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator, router, device)
        self._attribute = attribute
        self.entity_description = SENSOR_TYPES[attribute]
        self._attr_unique_id = f"{self._mac}-{attribute}"
        self._state = device.get(attribute)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._device.get(self._attribute) is not None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
        self._device = self._router.devices[self._mac]
        self._active = self._device["active"]
        if self._device.get(self._attribute) is not None:
            self._state = self._device[self._attribute]


class NetgearRouterSensorEntity(NetgearRouterCoordinatorEntity, RestoreSensor):
    """Representation of a device connected to a Netgear router."""

    _attr_entity_registry_enabled_default = False
    entity_description: NetgearSensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: NetgearRouter,
        entity_description: NetgearSensorEntityDescription,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator, router)
        self.entity_description = entity_description
        self._attr_unique_id = f"{router.serial_number}-{entity_description.key}-{entity_description.index}"

        self._value: StateType | date | datetime | Decimal = None
        self.async_update_device()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
