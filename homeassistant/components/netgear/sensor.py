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
from homeassistant.const import (
    DATA_MEGABYTES,
    DATA_RATE_MEGABITS_PER_SECOND,
    PERCENTAGE,
    TIME_MILLISECONDS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    KEY_COORDINATOR,
    KEY_COORDINATOR_LINK,
    KEY_COORDINATOR_SPEED,
    KEY_COORDINATOR_TRAFFIC,
    KEY_COORDINATOR_UTIL,
    KEY_ROUTER,
)
from .router import NetgearDeviceEntity, NetgearRouter, NetgearRouterEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "type": SensorEntityDescription(
        key="type",
        name="link type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lan",
    ),
    "link_rate": SensorEntityDescription(
        key="link_rate",
        name="link rate",
        native_unit_of_measurement="Mbps",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:speedometer",
    ),
    "signal": SensorEntityDescription(
        key="signal",
        name="signal strength",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "ssid": SensorEntityDescription(
        key="ssid",
        name="ssid",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:wifi-marker",
    ),
    "conn_ap_mac": SensorEntityDescription(
        key="conn_ap_mac",
        name="access point mac",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:router-network",
    ),
}


@dataclass
class NetgearSensorEntityDescription(SensorEntityDescription):
    """Class describing Netgear sensor entities."""

    value: Callable = lambda data: data
    index: int = 0


SENSOR_TRAFFIC_TYPES = [
    NetgearSensorEntityDescription(
        key="NewTodayUpload",
        name="Upload today",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
    ),
    NetgearSensorEntityDescription(
        key="NewTodayDownload",
        name="Download today",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
    ),
    NetgearSensorEntityDescription(
        key="NewYesterdayUpload",
        name="Upload yesterday",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
    ),
    NetgearSensorEntityDescription(
        key="NewYesterdayDownload",
        name="Download yesterday",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
    ),
    NetgearSensorEntityDescription(
        key="NewWeekUpload",
        name="Upload week",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
        index=0,
        value=lambda data: data[0],
    ),
    NetgearSensorEntityDescription(
        key="NewWeekUpload",
        name="Upload week average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
        index=1,
        value=lambda data: data[1],
    ),
    NetgearSensorEntityDescription(
        key="NewWeekDownload",
        name="Download week",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
        index=0,
        value=lambda data: data[0],
    ),
    NetgearSensorEntityDescription(
        key="NewWeekDownload",
        name="Download week average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
        index=1,
        value=lambda data: data[1],
    ),
    NetgearSensorEntityDescription(
        key="NewMonthUpload",
        name="Upload month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
        index=0,
        value=lambda data: data[0],
    ),
    NetgearSensorEntityDescription(
        key="NewMonthUpload",
        name="Upload month average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
        index=1,
        value=lambda data: data[1],
    ),
    NetgearSensorEntityDescription(
        key="NewMonthDownload",
        name="Download month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
        index=0,
        value=lambda data: data[0],
    ),
    NetgearSensorEntityDescription(
        key="NewMonthDownload",
        name="Download month average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
        index=1,
        value=lambda data: data[1],
    ),
    NetgearSensorEntityDescription(
        key="NewLastMonthUpload",
        name="Upload last month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
        index=0,
        value=lambda data: data[0],
    ),
    NetgearSensorEntityDescription(
        key="NewLastMonthUpload",
        name="Upload last month average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:upload",
        index=1,
        value=lambda data: data[1],
    ),
    NetgearSensorEntityDescription(
        key="NewLastMonthDownload",
        name="Download last month",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
        index=0,
        value=lambda data: data[0],
    ),
    NetgearSensorEntityDescription(
        key="NewLastMonthDownload",
        name="Download last month average",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
        icon="mdi:download",
        index=1,
        value=lambda data: data[1],
    ),
]

SENSOR_SPEED_TYPES = [
    NetgearSensorEntityDescription(
        key="NewOOKLAUplinkBandwidth",
        name="Uplink Bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        icon="mdi:upload",
    ),
    NetgearSensorEntityDescription(
        key="NewOOKLADownlinkBandwidth",
        name="Downlink Bandwidth",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        icon="mdi:download",
    ),
    NetgearSensorEntityDescription(
        key="AveragePing",
        name="Average Ping",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=TIME_MILLISECONDS,
        icon="mdi:wan",
    ),
]

SENSOR_UTILIZATION = [
    NetgearSensorEntityDescription(
        key="NewCPUUtilization",
        name="CPU Utilization",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:cpu-64-bit",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    NetgearSensorEntityDescription(
        key="NewMemoryUtilization",
        name="Memory Utilization",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

SENSOR_LINK_TYPES = [
    NetgearSensorEntityDescription(
        key="NewEthernetLinkStatus",
        name="Ethernet Link Status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:ethernet",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Netgear component."""
    router = hass.data[DOMAIN][entry.entry_id][KEY_ROUTER]
    coordinator = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR]
    coordinator_traffic = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR_TRAFFIC]
    coordinator_speed = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR_SPEED]
    coordinator_utilization = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR_UTIL]
    coordinator_link = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR_LINK]

    # Router entities
    router_entities = []

    for description in SENSOR_TRAFFIC_TYPES:
        router_entities.append(
            NetgearRouterSensorEntity(coordinator_traffic, router, description)
        )

    for description in SENSOR_SPEED_TYPES:
        router_entities.append(
            NetgearRouterSensorEntity(coordinator_speed, router, description)
        )

    for description in SENSOR_UTILIZATION:
        router_entities.append(
            NetgearRouterSensorEntity(coordinator_utilization, router, description)
        )

    for description in SENSOR_LINK_TYPES:
        router_entities.append(
            NetgearRouterSensorEntity(coordinator_link, router, description)
        )

    async_add_entities(router_entities)

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

        new_entities = []

        for mac, device in router.devices.items():
            if mac in tracked:
                continue

            new_entities.extend(
                [
                    NetgearSensorEntity(coordinator, router, device, attribute)
                    for attribute in sensors
                ]
            )
            tracked.add(mac)

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(new_device_callback))

    coordinator.data = True
    new_device_callback()


class NetgearSensorEntity(NetgearDeviceEntity, SensorEntity):
    """Representation of a device connected to a Netgear router."""

    _attr_entity_registry_enabled_default = False

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
        self.entity_description = SENSOR_TYPES[self._attribute]
        self._name = f"{self.get_device_name()} {self.entity_description.name}"
        self._unique_id = f"{self._mac}-{self._attribute}"
        self._state = self._device.get(self._attribute)

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


class NetgearRouterSensorEntity(NetgearRouterEntity, RestoreSensor):
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
        self._name = f"{router.device_name} {entity_description.name}"
        self._unique_id = f"{router.serial_number}-{entity_description.key}-{entity_description.index}"

        self._value: StateType | date | datetime | Decimal = None
        self.async_update_device()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._value

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if self.coordinator.data is None:
            sensor_data = await self.async_get_last_sensor_data()
            if sensor_data is not None:
                self._value = sensor_data.native_value

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
        if self.coordinator.data is None:
            return

        data = self.coordinator.data.get(self.entity_description.key)
        if data is None:
            self._value = None
            _LOGGER.debug(
                "key '%s' not in Netgear router response '%s'",
                self.entity_description.key,
                data,
            )
            return

        self._value = self.entity_description.value(data)
