"""Support for TPLink Omada binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tplink_omada_client.definitions import DeviceStatus, DeviceStatusCategory
from tplink_omada_client.devices import OmadaListDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import OmadaConfigEntry
from .const import OmadaDeviceStatus
from .coordinator import OmadaDevicesCoordinator
from .entity import OmadaDeviceEntity

# Useful low level status categories, mapped to a more descriptive status.
DEVICE_STATUS_MAP = {
    DeviceStatus.PROVISIONING: OmadaDeviceStatus.PENDING,
    DeviceStatus.CONFIGURING: OmadaDeviceStatus.PENDING,
    DeviceStatus.UPGRADING: OmadaDeviceStatus.PENDING,
    DeviceStatus.REBOOTING: OmadaDeviceStatus.PENDING,
    DeviceStatus.ADOPT_FAILED: OmadaDeviceStatus.ADOPT_FAILED,
    DeviceStatus.ADOPT_FAILED_WIRELESS: OmadaDeviceStatus.ADOPT_FAILED,
    DeviceStatus.MANAGED_EXTERNALLY: OmadaDeviceStatus.MANAGED_EXTERNALLY,
    DeviceStatus.MANAGED_EXTERNALLY_WIRELESS: OmadaDeviceStatus.MANAGED_EXTERNALLY,
}

# High level status categories, suitable for most device statuses.
DEVICE_STATUS_CATEGORY_MAP = {
    DeviceStatusCategory.DISCONNECTED: OmadaDeviceStatus.DISCONNECTED,
    DeviceStatusCategory.CONNECTED: OmadaDeviceStatus.CONNECTED,
    DeviceStatusCategory.PENDING: OmadaDeviceStatus.PENDING,
    DeviceStatusCategory.HEARTBEAT_MISSED: OmadaDeviceStatus.HEARTBEAT_MISSED,
    DeviceStatusCategory.ISOLATED: OmadaDeviceStatus.ISOLATED,
}


def _map_device_status(device: OmadaListDevice) -> str:
    """Map the API device status to the best available descriptive device status."""
    return DEVICE_STATUS_MAP.get(
        device.status,
        DEVICE_STATUS_CATEGORY_MAP.get(
            device.status_category, OmadaDeviceStatus.UNKNOWN
        ).value,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    controller = config_entry.runtime_data

    devices_coordinator = controller.devices_coordinator

    entities: list[OmadaDeviceEntity] = []
    for device in devices_coordinator.data.values():
        entities.extend(
            OmadaDeviceSensor(devices_coordinator, device, desc)
            for desc in OMADA_DEVICE_SENSORS
            if desc.exists_func(device)
        )

    async_add_entities(entities)


@dataclass(frozen=True, kw_only=True)
class OmadaDeviceSensorEntityDescription(SensorEntityDescription):
    """Entity description for a status derived from an Omada device in the device list."""

    exists_func: Callable[[OmadaListDevice], bool] = lambda _: True
    update_func: Callable[[OmadaListDevice], StateType]


OMADA_DEVICE_SENSORS: list[OmadaDeviceSensorEntityDescription] = [
    OmadaDeviceSensorEntityDescription(
        key="device_status",
        translation_key="device_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_func=_map_device_status,
        options=[v.value for v in OmadaDeviceStatus],
        has_entity_name=True,
    ),
    OmadaDeviceSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        update_func=lambda device: device.cpu_usage,
        has_entity_name=True,
    ),
    OmadaDeviceSensorEntityDescription(
        key="mem_usage",
        translation_key="mem_usage",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        update_func=lambda device: device.mem_usage,
        has_entity_name=True,
    ),
]


class OmadaDeviceSensor(OmadaDeviceEntity[OmadaDevicesCoordinator], SensorEntity):
    """Sensor for property of a generic Omada device."""

    entity_description: OmadaDeviceSensorEntityDescription

    def __init__(
        self,
        coordinator: OmadaDevicesCoordinator,
        device: OmadaListDevice,
        entity_description: OmadaDeviceSensorEntityDescription,
    ) -> None:
        """Initialize the device sensor."""
        super().__init__(coordinator, device)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.mac}_{entity_description.key}"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._do_update()

    def _do_update(self) -> None:
        self.device = self.coordinator.data[self.device.mac]
        self._attr_native_value = self.entity_description.update_func(self.device)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._do_update()
        self.async_write_ha_state()
