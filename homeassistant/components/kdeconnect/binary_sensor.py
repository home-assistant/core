"""Support for KDE Connect binary sensors."""
from typing import cast

from pykdeconnect.client import KdeConnectClient
from pykdeconnect.devices import KdeConnectDevice
from pykdeconnect.plugin_registry import PluginRegistry
from pykdeconnect.plugins.battery import BatteryReceiverPlugin

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KdeConnectEntity, KdeConnectPluginEntity
from .const import DATA_KEY_CLIENT, DATA_KEY_DEVICES, DOMAIN

BINARY_SENSOR_TYPES = [
    BinarySensorEntityDescription(
        key="battery_charging",
        name="Battery Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(
        key="battery_low",
        name="Battery Low",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
]

BINARY_SENSOR_PLUGINS = {
    "battery_charging": BatteryReceiverPlugin,
    "battery_low": BatteryReceiverPlugin,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the KDE Connect binary sensors."""
    client = cast(KdeConnectClient, hass.data[DOMAIN][DATA_KEY_CLIENT])
    device = cast(KdeConnectDevice, hass.data[DOMAIN][DATA_KEY_DEVICES][entry.entry_id])

    entities: list[BinarySensorEntity] = [
        KdeConnectPluginBinarySensor(device, client.plugin_registry, description)
        for description in BINARY_SENSOR_TYPES
    ]
    entities.append(KdeConnectConnectedSensor(device))

    async_add_entities(entities)


class KdeConnectPluginBinarySensor(KdeConnectPluginEntity, BinarySensorEntity):
    """A binary sensor using a KDE Connect plugin."""

    _attr_should_poll = False

    def __init__(
        self,
        device: KdeConnectDevice,
        plugin_registry: PluginRegistry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the battery charging sensor."""
        super().__init__(
            device, plugin_registry, BINARY_SENSOR_PLUGINS[description.key]
        )
        self.entity_description = description
        self._attr_name = f"{device.device_name} {description.name}"
        self._attr_unique_id = f"{device.device_id}/{description.key}"

        if description.key == "battery_charging":
            assert isinstance(self.plugin, BatteryReceiverPlugin)
            self.plugin.register_charging_changed_callback(self.on_state_changed)
        elif description.key == "battery_low":
            assert isinstance(self.plugin, BatteryReceiverPlugin)
            self.plugin.register_low_changed_callback(self.on_state_changed)
        else:
            assert False  # pragma: no cover

    def __del__(self) -> None:
        """Unregister callbacks."""
        if self.entity_description.key == "battery_charging":
            assert isinstance(self.plugin, BatteryReceiverPlugin)
            self.plugin.unregister_charging_changed_callback(self.on_state_changed)
        elif self.entity_description.key == "battery_low":
            assert isinstance(self.plugin, BatteryReceiverPlugin)
            self.plugin.unregister_low_changed_callback(self.on_state_changed)
        else:
            assert False  # pragma: no cover

    async def on_state_changed(self, state: bool) -> None:
        """Handle a state update."""
        self._attr_is_on = state
        self.async_schedule_update_ha_state()

    def restore_state(self, state: State) -> None:
        """Restore the state of the device on restart."""
        self._attr_is_on = state.state == STATE_ON


class KdeConnectConnectedSensor(KdeConnectEntity, BinarySensorEntity):
    """A binary sensor checking if a KDE Connect device is connected."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = False

    def __init__(self, device: KdeConnectDevice) -> None:
        """Initialize the device connected sensor."""
        super().__init__(device)

        self._attr_name = f"{device.device_name} Connected"
        self._attr_unique_id = f"{device.device_id}/connected"

        self._attr_is_on = device.is_connected

        device.register_device_connected_callback(self.on_device_connected)
        device.register_device_disconnected_callback(self.on_device_disconnected)

    def __del__(self) -> None:
        """Clean up callbacks on destruction."""
        self.device.unregister_device_connected_callback(self.on_device_connected)
        self.device.unregister_device_disconnected_callback(self.on_device_disconnected)

    async def on_device_connected(self) -> None:
        """Handle a device connection."""
        self._attr_is_on = True
        self.async_schedule_update_ha_state()

    async def on_device_disconnected(self) -> None:
        """Handle a device disconnection."""
        self._attr_is_on = False
        self.async_schedule_update_ha_state()

    def restore_state(self, state: State) -> None:
        """Do nothing.

        This sensor doesn't need to be restored, as it's data is always available.
        """
