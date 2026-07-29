"""Support for TPLink Omada binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from tplink_omada_client.definitions import DeviceStatus, DeviceStatusCategory, PortType
from tplink_omada_client.devices import (
    OmadaListDevice,
    OmadaSwitch,
    OmadaSwitchPortDetails,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import OmadaConfigEntry
from .const import OmadaDeviceStatus
from .coordinator import OmadaDevicesCoordinator, OmadaSwitchPortCoordinator
from .entity import OmadaDeviceEntity, get_switch_port_base_name

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OmadaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    controller = config_entry.runtime_data

    devices_coordinator = controller.devices_coordinator

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

    async def _create_switch_port_sensor_entities(
        device: OmadaListDevice,
    ) -> None:
        """Create sensor entities for a switch's ports."""
        switch = await controller.omada_client.get_switch(device)
        coordinator = controller.get_switch_port_coordinator(switch)
        await coordinator.async_refresh()

        entities: list[Entity] = [
            OmadaSwitchPortSensor(
                coordinator,
                switch,
                port,
                desc,
                port_name=get_switch_port_base_name(port),
            )
            for port in coordinator.data.values()
            for desc in OMADA_SWITCH_PORT_SENSORS
            if desc.exists_func(switch, port)
        ]
        async_add_entities(entities)

    await controller.async_register_device_entities(
        lambda d: (
            d.type == "switch" and d.status_category == DeviceStatusCategory.CONNECTED
        ),
        _create_switch_port_sensor_entities,
    )


@dataclass(frozen=True, kw_only=True)
class OmadaDeviceSensorEntityDescription(SensorEntityDescription):
    """Entity description for status from an Omada device."""

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


@dataclass(frozen=True, kw_only=True)
class OmadaSwitchPortSensorEntityDescription(SensorEntityDescription):
    """Entity description for a sensor derived from a switch port."""

    exists_func: Callable[[OmadaSwitch, OmadaSwitchPortDetails], bool] = lambda _, p: (
        True
    )
    update_func: Callable[[OmadaSwitchPortDetails], StateType]


OMADA_SWITCH_PORT_SENSORS: list[OmadaSwitchPortSensorEntityDescription] = [
    OmadaSwitchPortSensorEntityDescription(
        key="poe_power",
        translation_key="poe_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        exists_func=(
            lambda switch_device, port: (
                switch_device.device_capabilities.supports_poe
                and port.supports_poe
                and port.type != PortType.SFP
            )
        ),
        update_func=lambda p: p.port_status.poe_power,
    ),
]


class OmadaSwitchPortSensor(
    OmadaDeviceEntity[OmadaSwitchPortCoordinator], SensorEntity
):
    """Sensor for a property of a switch port."""

    entity_description: OmadaSwitchPortSensorEntityDescription

    def __init__(
        self,
        coordinator: OmadaSwitchPortCoordinator,
        device: OmadaSwitch,
        port: OmadaSwitchPortDetails,
        entity_description: OmadaSwitchPortSensorEntityDescription,
        port_name: str,
    ) -> None:
        """Initialize the switch port sensor."""
        super().__init__(coordinator, device)
        self.entity_description = entity_description
        self._port_id = port.port_id
        self._attr_unique_id = f"{device.mac}_{port.port_id}_{entity_description.key}"
        self._attr_translation_placeholders = {"port_name": port_name}

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.update_func(self.coordinator.data[self._port_id])
