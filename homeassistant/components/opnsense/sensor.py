"""Sensor platform for OPNsense routers."""

from collections import abc
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import OPNsenseConfigEntry, OPNsenseCoordinator
from .types import DeviceDetails

type OPNsenseRawValue = str | int | bool
type OPNsenseConvertedValue = datetime | str | None


def _convert_expires(value: OPNsenseRawValue) -> OPNsenseConvertedValue:
    """Convert expires value to a timestamp when possible."""
    # Use exact type check to exclude bool, which is a subclass of int.
    if type(value) is int and value > 0:
        return dt_util.utcnow() + timedelta(seconds=value)
    return None


def _convert_interface(value: OPNsenseRawValue) -> OPNsenseConvertedValue:
    """Convert interface value to a string."""
    if isinstance(value, str):
        return value
    return str(value)


@dataclass(frozen=True, kw_only=True)
class OPNsenseSensorEntityDescription(SensorEntityDescription):
    """Description of an OPNsense sensor entity."""

    data_key: str
    value_fn: abc.Callable[[OPNsenseRawValue], OPNsenseConvertedValue]


SENSOR_DESCRIPTIONS: tuple[OPNsenseSensorEntityDescription, ...] = (
    OPNsenseSensorEntityDescription(
        key="expires",
        translation_key="expires",
        data_key="expires",
        value_fn=_convert_expires,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    OPNsenseSensorEntityDescription(
        key="interface",
        translation_key="interface",
        data_key="intf_description",
        value_fn=_convert_interface,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OPNsenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities for OPNsense."""
    coordinator = entry.runtime_data.coordinator
    tracked_sensor_devices = entry.runtime_data.tracked_sensor_devices

    @callback
    def _async_add_new_entities() -> None:
        """Add entities for newly discovered devices."""
        if not coordinator.data:
            return

        entities: list[OPNsenseSensorEntity] = []
        for mac_address in coordinator.data:
            if mac_address in tracked_sensor_devices:
                continue
            entities.extend(
                OPNsenseSensorEntity(
                    coordinator,
                    mac_address,
                    sensor_description,
                )
                for sensor_description in SENSOR_DESCRIPTIONS
            )
            tracked_sensor_devices.add(mac_address)

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))

    _async_add_new_entities()


class OPNsenseSensorEntity(CoordinatorEntity[OPNsenseCoordinator], SensorEntity):
    """Representation of an OPNsense sensor for one tracked device."""

    _attr_has_entity_name = True
    entity_description: OPNsenseSensorEntityDescription

    def __init__(
        self,
        coordinator: OPNsenseCoordinator,
        mac_address: str,
        description: OPNsenseSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mac_address}_{description.key}"
        self._mac_address = mac_address
        connection = (dr.CONNECTION_NETWORK_MAC, mac_address)
        self._attr_device_info = dr.DeviceInfo(connections={connection})
        if not dr.async_get(coordinator.hass).async_get_device_by_connection(
            connection, coordinator.config_entry.entry_id
        ):
            self._attr_device_info["name"] = mac_address
        if self.available:
            device_data = self.device_data
            if device_data is not None:
                if hostname := device_data.get("hostname"):
                    self._attr_device_info["name"] = str(hostname)
                if manufacturer := device_data.get("manufacturer"):
                    self._attr_device_info["manufacturer"] = str(manufacturer)

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._mac_address in self.coordinator.data

    @property
    def device_data(self) -> DeviceDetails | None:
        """Return device data for current device."""
        return self.coordinator.data.get(self._mac_address)

    @property
    @override
    def native_value(self) -> datetime | str | None:
        """Return sensor value."""
        if not self.available:
            return None

        device_data = self.device_data
        if device_data is None:
            return None

        value = device_data.get(self.entity_description.data_key)
        if value is None:
            return None

        if value == "":
            return None

        return self.entity_description.value_fn(value)
