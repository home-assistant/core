"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""

from __future__ import annotations

import logging
from typing import Any

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
    UnitOfDataRate,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, WIFI_BANDS_TO_CONNECTIVITY, DeviceConnectivityType
from .entity import FreeboxHomeEntity
from .router import FreeboxConfigEntry, FreeboxRouter

_LOGGER = logging.getLogger(__name__)

CONNECTION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="rate_down",
        name="Freebox download speed",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        icon="mdi:download-network",
    ),
    SensorEntityDescription(
        key="rate_up",
        name="Freebox upload speed",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        icon="mdi:upload-network",
    ),
)

CALL_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="missed",
        name="Freebox missed calls",
        icon="mdi:phone-missed",
    ),
)

DISK_PARTITION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="partition_free_space",
        name="free space",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
    ),
)

DEVICE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="connectivity",
        name="Connectivity",
        device_class=SensorDeviceClass.ENUM,
        options=[e.value for e in DeviceConnectivityType.__members__.values()],
        icon="mdi:network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
    ),
)

WIFI_DEVICE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="wifi_signal_dbm",
        name="Wifi signal strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        icon="mdi:signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="wifi_signal_percentage",
        name="Wifi signal level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    router = entry.runtime_data
    entities: list[SensorEntity] = []

    _LOGGER.debug(
        "%s - %s - %s temperature sensors",
        router.name,
        router.mac,
        len(router.sensors_temperature),
    )
    entities = [
        FreeboxSensor(
            router,
            SensorEntityDescription(
                key=sensor_name,
                name=f"Freebox {sensor_name}",
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
        )
        for sensor_name in router.sensors_temperature
    ]

    entities.extend(
        [FreeboxSensor(router, description) for description in CONNECTION_SENSORS]
    )
    entities.extend(
        [FreeboxCallSensor(router, description) for description in CALL_SENSORS]
    )

    _LOGGER.debug("%s - %s - %s disk(s)", router.name, router.mac, len(router.disks))
    entities.extend(
        FreeboxDiskSensor(router, disk, partition, description)
        for disk in router.disks.values()
        for partition in disk["partitions"].values()
        for description in DISK_PARTITION_SENSORS
    )

    for node in router.home_devices.values():
        for endpoint in node["show_endpoints"]:
            if (
                endpoint["name"] == "battery"
                and endpoint["ep_type"] == "signal"
                and endpoint.get("value") is not None
            ):
                entities.append(FreeboxBatterySensor(hass, router, node, endpoint))

    for device in router.devices.values():
        if not device.get("persistent", False):
            continue
        entities.extend(
            FreeboxDeviceSensor(router, device, description)
            for description in DEVICE_SENSORS
        )
        if (
            connectivity_type := get_device_connectity_type(device)
        ) and connectivity_type != DeviceConnectivityType.ETHERNET:
            entities.extend(
                FreeboxDeviceSensor(router, device, description)
                for description in WIFI_DEVICE_SENSORS
            )
    if entities:
        async_add_entities(entities, True)


class FreeboxSensor(SensorEntity):
    """Representation of a Freebox sensor."""

    _attr_should_poll = False

    def __init__(
        self, router: FreeboxRouter, description: SensorEntityDescription
    ) -> None:
        """Initialize a Freebox sensor."""
        self.entity_description = description
        self._router = router
        self._attr_unique_id = f"{router.mac} {description.name}"
        self._attr_device_info = router.device_info

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox sensor."""
        state = self._router.sensors[self.entity_description.key]
        if self.native_unit_of_measurement == UnitOfDataRate.KILOBYTES_PER_SECOND:
            self._attr_native_value = round(state / 1000, 2)
        else:
            self._attr_native_value = state

    @callback
    def async_on_demand_update(self) -> None:
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_sensor_update,
                self.async_on_demand_update,
            )
        )


class FreeboxCallSensor(FreeboxSensor):
    """Representation of a Freebox call sensor."""

    def __init__(
        self, router: FreeboxRouter, description: SensorEntityDescription
    ) -> None:
        """Initialize a Freebox call sensor."""
        super().__init__(router, description)
        self._call_list_for_type: list[dict[str, Any]] = []

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox call sensor."""
        self._call_list_for_type = []
        if self._router.call_list:
            for call in self._router.call_list:
                if not call["new"]:
                    continue
                if self.entity_description.key == call["type"]:
                    self._call_list_for_type.append(call)

        self._attr_native_value = len(self._call_list_for_type)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            dt_util.utc_from_timestamp(call["datetime"]).isoformat(): call["name"]
            for call in self._call_list_for_type
        }


class FreeboxDiskSensor(FreeboxSensor):
    """Representation of a Freebox disk sensor."""

    def __init__(
        self,
        router: FreeboxRouter,
        disk: dict[str, Any],
        partition: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Freebox disk sensor."""
        super().__init__(router, description)
        self._disk_id = disk["id"]
        self._partition_id = partition["id"]
        self._attr_name = f"{partition['label']} {description.name}"
        self._attr_unique_id = (
            f"{router.mac} {description.key} {disk['id']} {partition['id']}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, disk["id"])},
            model=disk["model"],
            name=f"Disk {disk['id']}",
            sw_version=disk["firmware"],
            via_device=(
                DOMAIN,
                router.mac,
            ),
        )

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox disk sensor."""
        value = None
        disk: dict[str, Any] = self._router.disks[self._disk_id]
        partition: dict[str, Any] = disk["partitions"][self._partition_id]
        if partition.get("total_bytes"):
            value = round(partition["free_bytes"] * 100 / partition["total_bytes"], 2)
        self._attr_native_value = value


class FreeboxBatterySensor(FreeboxHomeEntity, SensorEntity):
    """Representation of a Freebox battery sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> int:
        """Return the current state of the device."""
        return self.get_value("signal", "battery")


class FreeboxDeviceSensor(FreeboxSensor):
    """Representation of a Freebox device sensor."""

    def __init__(
        self,
        router: FreeboxRouter,
        device: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Freebox device sensor."""
        super().__init__(router, description)
        self._device = device
        mac_address = device["l2ident"]["id"]
        self._attr_unique_id = f"{router.mac} {description.key} {mac_address}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            manufacturer=device["vendor_name"],
            name=device["primary_name"],
            via_device=(DOMAIN, router.mac),
            connections={(CONNECTION_NETWORK_MAC, mac_address)},
        )
        self._attr_name = f"{device['primary_name']} {description.name}"

    def async_update_state(self) -> None:
        """Update the Freebox device sensor."""
        if self.entity_description.key == "connectivity":
            self._attr_native_value = get_device_connectity_type(self._device)
        elif self.entity_description.key == "wifi_signal_dbm":
            self._attr_native_value = get_device_wifi_signal_strength_dbm(self._device)
        elif self.entity_description.key == "wifi_signal_percentage":
            self._attr_native_value = get_device_wifi_signal_strength_percentage(
                self._device
            )


def get_device_connectity_type(device: dict[str, Any]) -> str | None:
    """Get the connectivity type of a device."""
    result = None
    access_point = device.get("access_point", {})
    if connectivity_type := access_point.get("connectivity_type"):
        if connectivity_type == "wifi":
            wifi_information = access_point.get("wifi_information", {})
            band = wifi_information.get("band", "")
            result = WIFI_BANDS_TO_CONNECTIVITY.get(band, DeviceConnectivityType.WIFI)
        if connectivity_type == "ethernet":
            result = DeviceConnectivityType.ETHERNET
    return result.value if result else None


def get_device_wifi_signal_strength_dbm(device: dict[str, Any]) -> int | None:
    """Get the wifi signal strength of a device in dBm."""
    access_point = device.get("access_point", {})
    wifi_information = access_point.get("wifi_information", {})
    return wifi_information.get("signal")


def get_device_wifi_signal_strength_percentage(device: dict[str, Any]) -> int | None:
    """Get the wifi signal strength of a device in percentage."""
    if dbm := get_device_wifi_signal_strength_dbm(device):
        return min(max(2 * (dbm + 100), 0), 100)
    return None
