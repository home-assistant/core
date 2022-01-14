"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_RATE_KILOBYTES_PER_SECOND, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import (
    CALL_SENSORS,
    CONNECTION_SENSORS,
    DISK_PARTITION_SENSORS,
    DOMAIN,
    HOME_NODES_ALARM_REMOTE_KEY,
    HOME_NODES_SENSORS,
)
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    router = hass.data[DOMAIN][entry.unique_id]
    entities = []

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
                native_unit_of_measurement=TEMP_CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
            ),
            router.mac,
        )
        for sensor_name in router.sensors_temperature
    ]

    entities.extend(
        [
            FreeboxSensor(router, description, router.mac)
            for description in CONNECTION_SENSORS
        ]
    )
    entities.extend(
        [FreeboxCallSensor(router, description) for description in CALL_SENSORS]
    )

    _LOGGER.debug("%s - %s - %s disk(s)", router.name, router.mac, len(router.disks))
    entities.extend(
        FreeboxDiskSensor(router, disk, partition, description)
        for disk in router.disks.values()
        for partition in disk["partitions"]
        for description in DISK_PARTITION_SENSORS
    )

    _LOGGER.debug(
        "%s - %s - %s home node(s)", router.name, router.mac, len(router.home_nodes)
    )

    for home_node in router.home_nodes.values():
        for endpoint in home_node.get("show_endpoints"):
            if (
                endpoint["ep_type"] == "signal"
                and endpoint["name"] in HOME_NODES_SENSORS.keys()
            ):
                entities.append(
                    FreeboxHomeNodeSensor(
                        router,
                        home_node,
                        endpoint,
                        HOME_NODES_SENSORS[endpoint["name"]],
                    )
                )

    async_add_entities(entities, True)


class FreeboxSensor(SensorEntity):
    """Representation of a Freebox sensor."""

    _attr_should_poll = False

    def __init__(
        self, router: FreeboxRouter, description: SensorEntityDescription, unik: Any
    ) -> None:
        """Initialize a Freebox sensor."""
        self.entity_description = description
        self._router = router
        self._unik = unik
        self._attr_unique_id = f"{router.mac} {description.name} {unik}"

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox sensor."""
        state = self._router.sensors[self.entity_description.key]
        if self.native_unit_of_measurement == DATA_RATE_KILOBYTES_PER_SECOND:
            self._attr_native_value = round(state / 1000, 2)
        else:
            self._attr_native_value = state

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._router.device_info

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
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
        super().__init__(router, description, router.mac)
        self._call_list_for_type = []

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
        super().__init__(router, description, f"{disk['id']} {partition['id']}")
        self._disk = disk
        self._partition = partition
        self._attr_name = f"{partition['label']} {description.name}"
        self._unique_id = f"{self._router.mac} {description.key} {self._disk['id']} {self._partition['id']}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._disk["id"])},
            model=self._disk["model"],
            name=f"Disk {self._disk['id']}",
            sw_version=self._disk["firmware"],
            via_device=(
                DOMAIN,
                self._router.mac,
            ),
            vendor_name="Freebox SAS",
            manufacturer="Freebox SAS",
        )

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox disk sensor."""
        value = None
        current_disk = self._router.disks.get(self._disk.get("id"))
        for partition in current_disk["partitions"]:
            if self._partition["id"] == partition["id"]:
                value = round(
                    partition["free_bytes"] * 100 / partition["total_bytes"], 2
                )
        self._attr_native_value = value


class FreeboxHomeNodeSensor(FreeboxSensor):
    """Representation of a Freebox Home node sensor."""

    def __init__(
        self,
        router: FreeboxRouter,
        home_node: dict[str, Any],
        endpoint: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Freebox Home node sensor."""
        super().__init__(router, description, f"{home_node['id']} {endpoint['id']}")
        self._home_node = home_node
        self._endpoint = endpoint
        self._attr_name = f"{home_node['label']} {description.name}"
        self._unique_id = f"{self._router.mac} {description.key} {self._home_node['id']} {endpoint['id']}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        fw_version = None
        if "props" in self._home_node:
            props = self._home_node["props"]
            if "FwVersion" in props:
                fw_version = props["FwVersion"]

        return DeviceInfo(
            identifiers={(DOMAIN, self._home_node["id"])},
            model=f'{self._home_node["category"]}',
            name=f"{self._home_node['label']}",
            sw_version=fw_version,
            via_device=(
                DOMAIN,
                self._router.mac,
            ),
            vendor_name="Freebox SAS",
            manufacturer="Freebox SAS",
        )

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox Home node sensor."""
        value = None

        current_home_node = self._router.home_nodes.get(self._home_node.get("id"))
        if current_home_node.get("show_endpoints"):
            for end_point in current_home_node["show_endpoints"]:
                if self._endpoint["id"] == end_point["id"]:
                    if self._endpoint["name"] == "pushed":
                        if len(end_point.get("history")) > 0:
                            # Get the latest button pushed as pool mode is a mess
                            value = end_point.get("history")[-1].get("value")
                            value = HOME_NODES_ALARM_REMOTE_KEY[int(value) - 1]
                    else:
                        value = end_point["value"]
                    break

        self._attr_native_value = value
