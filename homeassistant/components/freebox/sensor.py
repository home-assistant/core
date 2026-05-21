"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""

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
    EntityCategory,
    UnitOfDataRate,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import FreeboxHomeEntity
from .router import FreeboxConfigEntry, FreeboxRouter

_LOGGER = logging.getLogger(__name__)

CONNECTION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="rate_down",
        translation_key="rate_down",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
    ),
    SensorEntityDescription(
        key="rate_up",
        translation_key="rate_up",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
    ),
)

CALL_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="missed",
        translation_key="missed",
        native_unit_of_measurement="calls",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

DISK_PARTITION_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="partition_free_space",
        translation_key="partition_free_space",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    router = entry.runtime_data

    _LOGGER.debug(
        "%s - %s - %s temperature sensors",
        router.name,
        router.mac,
        len(router.sensors_temperature),
    )
    entities: list[SensorEntity] = [
        FreeboxSensor(
            router,
            SensorEntityDescription(
                key=sensor_id,
                name=sensor_name,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        )
        for sensor_id, sensor_name in router.sensors_temperature_names.items()
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

    entities.extend(
        FreeboxBatterySensor(router, node, endpoint)
        for node in router.home_devices.values()
        for endpoint in node["show_endpoints"]
        if (
            endpoint["name"] == "battery"
            and endpoint["ep_type"] == "signal"
            and endpoint.get("value") is not None
        )
    )

    if entities:
        async_add_entities(entities, True)


class FreeboxSensor(SensorEntity):
    """Representation of a Freebox sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, router: FreeboxRouter, description: SensorEntityDescription
    ) -> None:
        """Initialize a Freebox sensor."""
        self.entity_description = description
        self._router = router
        self._attr_unique_id = f"{router.mac} {description.key}"
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
        self._attr_translation_placeholders = {"partition": partition["label"]}
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
