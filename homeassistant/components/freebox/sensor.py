"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_RATE_KILOBYTES_PER_SECOND
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.dt as dt_util

from .const import (
    CALL_SENSORS,
    CONNECTION_SENSORS,
    DISK_PARTITION_SENSORS,
    DOMAIN,
    SENSOR_DEVICE_CLASS,
    SENSOR_ICON,
    SENSOR_NAME,
    SENSOR_UNIT,
    TEMPERATURE_SENSOR_TEMPLATE,
)
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
    for sensor_name in router.sensors_temperature:
        entities.append(
            FreeboxSensor(
                router,
                sensor_name,
                {**TEMPERATURE_SENSOR_TEMPLATE, SENSOR_NAME: f"Freebox {sensor_name}"},
            )
        )

    for sensor_key in CONNECTION_SENSORS:
        entities.append(
            FreeboxSensor(router, sensor_key, CONNECTION_SENSORS[sensor_key])
        )

    for sensor_key in CALL_SENSORS:
        entities.append(FreeboxCallSensor(router, sensor_key, CALL_SENSORS[sensor_key]))

    _LOGGER.debug("%s - %s - %s disk(s)", router.name, router.mac, len(router.disks))
    for disk in router.disks.values():
        for partition in disk["partitions"]:
            for sensor_key in DISK_PARTITION_SENSORS:
                entities.append(
                    FreeboxDiskSensor(
                        router,
                        disk,
                        partition,
                        sensor_key,
                        DISK_PARTITION_SENSORS[sensor_key],
                    )
                )

    async_add_entities(entities, True)


class FreeboxSensor(SensorEntity):
    """Representation of a Freebox sensor."""

    def __init__(
        self, router: FreeboxRouter, sensor_type: str, sensor: dict[str, any]
    ) -> None:
        """Initialize a Freebox sensor."""
        self._state = None
        self._router = router
        self._sensor_type = sensor_type
        self._name = sensor[SENSOR_NAME]
        self._unit = sensor[SENSOR_UNIT]
        self._icon = sensor[SENSOR_ICON]
        self._device_class = sensor[SENSOR_DEVICE_CLASS]
        self._unique_id = f"{self._router.mac} {self._name}"

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox sensor."""
        state = self._router.sensors[self._sensor_type]
        if self._unit == DATA_RATE_KILOBYTES_PER_SECOND:
            self._state = round(state / 1000, 2)
        else:
            self._state = state

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit."""
        return self._unit

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Return the device_class."""
        return self._device_class

    @property
    def device_info(self) -> dict[str, any]:
        """Return the device information."""
        return self._router.device_info

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

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
        self, router: FreeboxRouter, sensor_type: str, sensor: dict[str, any]
    ) -> None:
        """Initialize a Freebox call sensor."""
        super().__init__(router, sensor_type, sensor)
        self._call_list_for_type = []

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox call sensor."""
        self._call_list_for_type = []
        if self._router.call_list:
            for call in self._router.call_list:
                if not call["new"]:
                    continue
                if call["type"] == self._sensor_type:
                    self._call_list_for_type.append(call)

        self._state = len(self._call_list_for_type)

    @property
    def extra_state_attributes(self) -> dict[str, any]:
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
        disk: dict[str, any],
        partition: dict[str, any],
        sensor_type: str,
        sensor: dict[str, any],
    ) -> None:
        """Initialize a Freebox disk sensor."""
        super().__init__(router, sensor_type, sensor)
        self._disk = disk
        self._partition = partition
        self._name = f"{partition['label']} {sensor[SENSOR_NAME]}"
        self._unique_id = f"{self._router.mac} {sensor_type} {self._disk['id']} {self._partition['id']}"

    @property
    def device_info(self) -> dict[str, any]:
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
        self._state = round(
            self._partition["free_bytes"] * 100 / self._partition["total_bytes"], 2
        )
