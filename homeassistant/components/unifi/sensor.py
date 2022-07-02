"""Sensor platform for UniFi Network integration.

Support for bandwidth sensors of network clients.
Support for uptime sensors of network clients.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiounifi.models.device import Device as UniFiDevice

from homeassistant.components.sensor import (
    DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_MEGABYTES, PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import ATTR_MANUFACTURER, DOMAIN as UNIFI_DOMAIN
from .controller import UniFiController
from .unifi_client import UniFiClient
from .unifi_entity_base import UniFiBase

CPU_TEMPERATURE_SENSOR = "cpu_temperature"
CPU_UTILIZATION_SENSOR = "cpu_utilization"
FAN_LEVEL_SENSOR = "fan_level"
LOCAL_TEMPERATURE_SENSOR = "local_temperature"
MEMORY_UTILIZATION_SENSOR = "memory_utilization"
PHY_TEMPERATURE_SENSOR = "phy_temperature"
RX_SENSOR = "rx"
TEMPERATURE_SENSOR = "temperature"
TX_SENSOR = "tx"
UPTIME_SENSOR = "uptime"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Network integration."""
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.entities[DOMAIN] = {
        RX_SENSOR: set(),
        TX_SENSOR: set(),
        UPTIME_SENSOR: set(),
        **{sensor.key: set() for sensor in DEVICE_SENSORS},
    }

    @callback
    def items_added(
        clients: set = controller.api.clients, devices: set = controller.api.devices
    ) -> None:
        """Update the values of the controller."""
        if controller.option_allow_bandwidth_sensors:
            add_bandwidth_entities(controller, async_add_entities, clients)

        if controller.option_allow_uptime_sensors:
            add_uptime_entities(controller, async_add_entities, clients)

        add_device_entities(controller, async_add_entities, devices)

    for signal in (controller.signal_update, controller.signal_options_update):
        config_entry.async_on_unload(
            async_dispatcher_connect(hass, signal, items_added)
        )

    items_added()


@callback
def add_bandwidth_entities(controller, async_add_entities, clients):
    """Add new sensor entities from the controller."""
    sensors = []

    for mac in clients:
        for sensor_class in (UniFiRxBandwidthSensor, UniFiTxBandwidthSensor):
            if mac in controller.entities[DOMAIN][sensor_class.TYPE]:
                continue

            client = controller.api.clients[mac]
            sensors.append(sensor_class(client, controller))

    if sensors:
        async_add_entities(sensors)


@callback
def add_uptime_entities(controller, async_add_entities, clients):
    """Add new sensor entities from the controller."""
    sensors = []

    for mac in clients:
        if mac in controller.entities[DOMAIN][UniFiUpTimeSensor.TYPE]:
            continue

        client = controller.api.clients[mac]
        sensors.append(UniFiUpTimeSensor(client, controller))

    if sensors:
        async_add_entities(sensors)


@callback
def add_device_entities(
    controller: UniFiController,
    async_add_entities: AddEntitiesCallback,
    devices: set[str],
) -> None:
    """Add new device sensor entities from the controller."""
    sensors = []

    for mac in devices:
        device = controller.api.devices[mac]

        for sensor in DEVICE_SENSORS:
            if mac in controller.entities[UniFiDeviceSensor.DOMAIN][sensor.key]:
                continue

            if not sensor.is_enabled(device):
                continue

            sensors.append(UniFiDeviceSensor(device, controller, sensor))

    if sensors:
        async_add_entities(sensors)


class UniFiBandwidthSensor(UniFiClient, SensorEntity):
    """UniFi Network bandwidth sensor base class."""

    DOMAIN = DOMAIN

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = DATA_MEGABYTES

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return f"{super().name} {self.TYPE.upper()}"

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_allow_bandwidth_sensors:
            await self.remove_item({self.client.mac})


class UniFiRxBandwidthSensor(UniFiBandwidthSensor):
    """Receiving bandwidth sensor."""

    TYPE = RX_SENSOR

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_rx_bytes_r / 1000000
        return self.client.rx_bytes_r / 1000000


class UniFiTxBandwidthSensor(UniFiBandwidthSensor):
    """Transmitting bandwidth sensor."""

    TYPE = TX_SENSOR

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        if self._is_wired:
            return self.client.wired_tx_bytes_r / 1000000
        return self.client.tx_bytes_r / 1000000


class UniFiUpTimeSensor(UniFiClient, SensorEntity):
    """UniFi Network client uptime sensor."""

    DOMAIN = DOMAIN
    TYPE = UPTIME_SENSOR

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client, controller):
        """Set up tracked client."""
        super().__init__(client, controller)

        self.last_updated_time = self.client.uptime

    @callback
    def async_update_callback(self) -> None:
        """Update sensor when time has changed significantly.

        This will help avoid unnecessary updates to the state machine.
        """
        update_state = True

        if self.client.uptime < 1000000000:
            if self.client.uptime > self.last_updated_time:
                update_state = False
        else:
            if self.client.uptime <= self.last_updated_time:
                update_state = False

        self.last_updated_time = self.client.uptime

        if not update_state:
            return

        super().async_update_callback()

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return f"{super().name} {self.TYPE.capitalize()}"

    @property
    def native_value(self) -> datetime:
        """Return the uptime of the client."""
        if self.client.uptime < 1000000000:
            return dt_util.now() - timedelta(seconds=self.client.uptime)
        return dt_util.utc_from_timestamp(float(self.client.uptime))

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_allow_uptime_sensors:
            await self.remove_item({self.client.mac})


@dataclass
class UniFiDeviceSensorEntityDescription(SensorEntityDescription):
    """Describes UniFi device sensor entities."""

    enabled: str | None = None
    value_fn: Callable[[UniFiDevice], StateType | datetime] | None = None

    def get_value(self, device: UniFiDevice) -> StateType | datetime:
        """Return value from UniFi device."""
        if self.value_fn is not None:
            return self.value_fn(device)

        return None

    def is_enabled(self, device: UniFiDevice) -> bool:
        """Return whether the entity should be enabled."""
        if self.enabled is None:
            return True

        return device.raw.get(self.enabled, False)


def _get_device_cpu_utilization(device: UniFiDevice) -> float | None:
    return float(device.raw.get("system-stats", {}).get("cpu"))


def _get_device_memory_utilization(device: UniFiDevice) -> float | None:
    return float(device.raw.get("system-stats", {}).get("mem"))


def _get_device_uptime(device: UniFiDevice) -> datetime:
    return dt_util.now() - timedelta(seconds=device.raw["uptime"])


def _get_device_general_temperature(device: UniFiDevice) -> int | None:
    return device.raw.get("general_temperature")


def _get_device_temperature(device: UniFiDevice, name: str) -> float | None:
    return next(
        (
            temperature["value"]
            for temperature in device.raw.get("temperatures", [])
            if temperature["name"] == name
        ),
        None,
    )


def _get_device_cpu_temperature(device: UniFiDevice) -> float | None:
    return _get_device_temperature(device, "CPU")


def _get_device_local_temperature(device: UniFiDevice) -> float | None:
    return _get_device_temperature(device, "Local")


def _get_device_phy_temperature(device: UniFiDevice) -> float | None:
    return _get_device_temperature(device, "PHY")


def _get_device_fan_level(device: UniFiDevice) -> int | None:
    return device.raw.get("fan_level")


DEVICE_SENSORS: tuple[UniFiDeviceSensorEntityDescription, ...] = (
    UniFiDeviceSensorEntityDescription(
        key=CPU_UTILIZATION_SENSOR,
        name="CPU Utilization",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:speedometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        enabled="system-stats",
        value_fn=_get_device_cpu_utilization,
    ),
    UniFiDeviceSensorEntityDescription(
        key=MEMORY_UTILIZATION_SENSOR,
        name="Memory Utilization",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        enabled="system-stats",
        value_fn=_get_device_memory_utilization,
    ),
    UniFiDeviceSensorEntityDescription(
        key=UPTIME_SENSOR,
        name="Uptime",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_get_device_uptime,
    ),
    UniFiDeviceSensorEntityDescription(
        key=TEMPERATURE_SENSOR,
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        enabled="has_temperature",
        value_fn=_get_device_general_temperature,
    ),
    UniFiDeviceSensorEntityDescription(
        key=CPU_TEMPERATURE_SENSOR,
        name="CPU Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        enabled="temperatures",
        value_fn=_get_device_cpu_temperature,
    ),
    UniFiDeviceSensorEntityDescription(
        key=LOCAL_TEMPERATURE_SENSOR,
        name="Local Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        enabled="temperatures",
        value_fn=_get_device_local_temperature,
    ),
    UniFiDeviceSensorEntityDescription(
        key=PHY_TEMPERATURE_SENSOR,
        name="PHY Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        enabled="temperatures",
        value_fn=_get_device_phy_temperature,
    ),
    UniFiDeviceSensorEntityDescription(
        key=FAN_LEVEL_SENSOR,
        name="Fan Level",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        enabled="has_fan",
        value_fn=_get_device_fan_level,
    ),
)


class UniFiDeviceSensor(UniFiBase, SensorEntity):
    """Base class for UniFi device sensors."""

    DOMAIN = DOMAIN

    entity_description: UniFiDeviceSensorEntityDescription
    previous_native_value: StateType | datetime = None

    def __init__(
        self,
        device: UniFiDevice,
        controller: UniFiController,
        description: UniFiDeviceSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        # pylint: disable=invalid-name
        self.TYPE = description.key
        super().__init__(device, controller)
        self.device = self._item
        self.entity_description = description

        self._attr_unique_id = f"{self.device.mac}-{description.key}"
        self._attr_name = f"{self.device.name} {(description.name or '')}"

    @property
    def available(self) -> bool:
        """Return whether the device is available."""
        return self.controller.available and self.device.state != 0

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for the device registry."""
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            manufacturer=ATTR_MANUFACTURER,
            model=self.device.model,
            name=self.device.name,
            sw_version=self.device.version,
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the native value of the sensor."""
        return self.entity_description.get_value(self.device)

    @callback
    def async_update_callback(self) -> None:
        """Prevent sensor updates if value has not changed.

        This will help avoid unnecessary updates to the state machine.
        """

        if self.previous_native_value == self.native_value:
            return

        self.previous_native_value = self.native_value
        super().async_update_callback()

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        pass  # pylint: disable=unnecessary-pass
