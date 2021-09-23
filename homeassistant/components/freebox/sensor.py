"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_RATE_KILOBYTES_PER_SECOND,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
import homeassistant.util.dt as dt_util

from .const import CALL_SENSORS, CONNECTION_SENSORS, DISK_PARTITION_SENSORS, DOMAIN
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
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
                device_class=DEVICE_CLASS_TEMPERATURE,
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
        for partition in disk["partitions"]
        for description in DISK_PARTITION_SENSORS
    )

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
        super().__init__(router, description)
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
        super().__init__(router, description)
        self._disk = disk
        self._partition = partition
        self._attr_name = f"{partition['label']} {description.name}"
        self._unique_id = f"{self._router.mac} {description.key} {self._disk['id']} {self._partition['id']}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._disk["id"])},
            "name": f"Disk {self._disk['id']}",
            "model": self._disk["model"],
            "sw_version": self._disk["firmware"],
            "via_device": (
                DOMAIN,
                self._router.mac,
            ),
        }

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox disk sensor."""
        self._attr_native_value = round(
            self._partition["free_bytes"] * 100 / self._partition["total_bytes"], 2
        )
