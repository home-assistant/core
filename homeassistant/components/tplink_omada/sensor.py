"""Support for TPLink Omada binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from tplink_omada_client import OmadaControllerInfo
from tplink_omada_client.definitions import DeviceStatus, DeviceStatusCategory
from tplink_omada_client.devices import OmadaListDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OmadaConfigEntry
from .config_flow import CONF_SITE
from .const import DOMAIN, OmadaDeviceStatus
from .coordinator import OmadaControllerInfoCoordinator, OmadaDevicesCoordinator
from .entity import OmadaDeviceEntity

PARALLEL_UPDATES = 0

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


def _map_device_status(device: OmadaListDevice) -> str | None:
    """Map the API device status to the best available descriptive device status."""
    display_status = DEVICE_STATUS_MAP.get(
        device.status
    ) or DEVICE_STATUS_CATEGORY_MAP.get(device.status_category)
    return display_status.value if display_status else None


def _map_controller_status(controller_info: OmadaControllerInfo) -> str:
    """Map the controller info response to a device status."""
    if controller_info.configured is False:
        return OmadaDeviceStatus.DISCONNECTED.value
    return OmadaDeviceStatus.CONNECTED.value


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    controller = config_entry.runtime_data

    controller_info_coordinator = controller.controller_info_coordinator
    devices_coordinator = controller.devices_coordinator

    if _config_entry_owns_controller_entities(hass, config_entry):
        async_add_entities(
            [
                OmadaControllerSensor(controller_info_coordinator, desc)
                for desc in OMADA_CONTROLLER_SENSORS
            ]
        )

    async def _create_device_sensor_entities(
        device: OmadaListDevice,
    ) -> None:
        """Create sensor entities for a device."""
        async_add_entities(
            [
                OmadaDeviceSensor(devices_coordinator, device, desc)
                for desc in OMADA_DEVICE_SENSORS
                if desc.exists_func(device)
            ]
        )

    await controller.async_register_device_entities(
        lambda _: True,
        _create_device_sensor_entities,
    )


@dataclass(frozen=True, kw_only=True)
class OmadaDeviceSensorEntityDescription(SensorEntityDescription):
    """Entity description for status from an Omada device."""

    exists_func: Callable[[OmadaListDevice], bool] = lambda _: True
    update_func: Callable[[OmadaListDevice], StateType]


@dataclass(frozen=True, kw_only=True)
class OmadaControllerSensorEntityDescription(SensorEntityDescription):
    """Entity description for status from the Omada controller."""

    update_func: Callable[[OmadaControllerInfo], StateType]
    extra_attributes_func: Callable[[OmadaControllerInfo], dict[str, StateType]] = (
        lambda _: {}
    )


def _config_entry_controller_unique_id(config_entry: ConfigEntry) -> str | None:
    """Return the controller-level unique ID for a site config entry."""
    unique_id = config_entry.unique_id
    site_id = config_entry.data.get(CONF_SITE)

    if unique_id is None or not isinstance(site_id, str):
        return unique_id

    site_suffix = f"_{site_id}"
    if unique_id.endswith(site_suffix):
        return unique_id[: -len(site_suffix)]

    return unique_id


def _config_entry_owns_controller_entities(
    hass: HomeAssistant, config_entry: OmadaConfigEntry
) -> bool:
    """Return if this site entry should add the controller-level entities."""
    controller_unique_id = _config_entry_controller_unique_id(config_entry)
    controller_entries = [
        entry
        for entry in hass.config_entries.async_entries(
            DOMAIN, include_ignore=False, include_disabled=False
        )
        if _config_entry_controller_unique_id(entry) == controller_unique_id
    ]

    return (
        config_entry.entry_id
        == min(
            controller_entries, key=lambda entry: (entry.created_at, entry.entry_id)
        ).entry_id
    )


def _controller_status_attributes(
    controller_info: OmadaControllerInfo,
) -> dict[str, StateType]:
    """Return attributes for the controller status sensor."""
    return {
        "configured": controller_info.configured,
        "type": controller_info.type,
        "support_app": controller_info.support_app,
        "registered_root": controller_info.registered_root,
        "omadac_category": controller_info.omadac_category,
        "msp_mode": controller_info.msp_mode,
        "omada_cloud_url": controller_info.omada_cloud_url,
    }


OMADA_CONTROLLER_SENSORS: list[OmadaControllerSensorEntityDescription] = [
    OmadaControllerSensorEntityDescription(
        key="device_status",
        translation_key="device_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_func=_map_controller_status,
        extra_attributes_func=_controller_status_attributes,
        options=[
            OmadaDeviceStatus.DISCONNECTED.value,
            OmadaDeviceStatus.CONNECTED.value,
        ],
    ),
    OmadaControllerSensorEntityDescription(
        key="version",
        translation_key="controller_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        update_func=lambda controller_info: controller_info.controller_version,
    ),
    OmadaControllerSensorEntityDescription(
        key="api_version",
        translation_key="controller_api_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        update_func=lambda controller_info: controller_info.api_version,
    ),
]


OMADA_DEVICE_SENSORS: list[OmadaDeviceSensorEntityDescription] = [
    OmadaDeviceSensorEntityDescription(
        key="device_status",
        translation_key="device_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        update_func=_map_device_status,
        options=[v.value for v in OmadaDeviceStatus],
    ),
    OmadaDeviceSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        update_func=lambda device: device.cpu_usage,
    ),
    OmadaDeviceSensorEntityDescription(
        key="mem_usage",
        translation_key="mem_usage",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        update_func=lambda device: device.mem_usage,
    ),
]


class OmadaControllerSensor(
    CoordinatorEntity[OmadaControllerInfoCoordinator], SensorEntity
):
    """Sensor for a property of the Omada controller."""

    _attr_has_entity_name = True
    entity_description: OmadaControllerSensorEntityDescription

    def __init__(
        self,
        coordinator: OmadaControllerInfoCoordinator,
        entity_description: OmadaControllerSensorEntityDescription,
    ) -> None:
        """Initialize the controller sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.data.omadac_id}_{entity_description.key}"

    @property
    @override
    def device_info(self) -> dr.DeviceInfo:
        """Return device info for the Omada controller."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.omadac_id)},
            manufacturer="TP-Link",
            model="Omada Controller",
            name="Omada Controller",
            sw_version=self.coordinator.data.controller_version,
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, StateType]:
        """Return extra attributes for the sensor."""
        return self.entity_description.extra_attributes_func(self.coordinator.data)

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.update_func(self.coordinator.data)


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

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.update_func(
            self.coordinator.data[self.device.mac]
        )
