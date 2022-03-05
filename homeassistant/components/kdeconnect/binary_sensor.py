"""Support for KDE Connect binary sensors."""
from typing import cast

from pykdeconnect.client import KdeConnectClient
from pykdeconnect.devices import KdeConnectDevice
from pykdeconnect.plugin_registry import PluginRegistry
from pykdeconnect.plugins.battery import BatteryReceiverPlugin

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KdeConnectEntity
from .const import DATA_KEY_CLIENT, DATA_KEY_DEVICES, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the KDE Connect binary sensors."""
    client = cast(KdeConnectClient, hass.data[DOMAIN][DATA_KEY_CLIENT])
    device = cast(KdeConnectDevice, hass.data[DOMAIN][DATA_KEY_DEVICES][entry.entry_id])

    async_add_entities(
        [
            KdeConnectBatteryChargingSensor(device, client.plugin_registry),
            KdeConnectBatteryLowSensor(device, client.plugin_registry),
            KdeConnectConnectedSensor(device),
        ]
    )


class KdeConnectBatteryChargingSensor(KdeConnectEntity, BinarySensorEntity):
    """A binary sensor checking if a KDE Connect device is charging."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_should_poll = False

    device: KdeConnectDevice

    def __init__(
        self, device: KdeConnectDevice, plugin_registry: PluginRegistry
    ) -> None:
        """Initialize the battery charging sensor."""
        super().__init__(device)
        self.battery_plugin = plugin_registry.get_plugin(device, BatteryReceiverPlugin)
        self.battery_plugin.register_charging_changed_callback(self.on_battery_update)

        self._attr_name = f"{device.device_name} Battery Charging"
        self._attr_unique_id = f"{device.device_id}/battery_charging"

    def __del__(self) -> None:
        """Clean up callbacks on destruction."""
        self.battery_plugin.unregister_low_changed_callback(self.on_battery_update)

    async def on_battery_update(self, charging: bool) -> None:
        """Handle a battery update."""
        self._attr_is_on = charging
        self.async_schedule_update_ha_state()

    def restore_state(self, state: State) -> None:
        """Restore the state of the device on restart."""
        self._attr_is_on = state.state == STATE_ON


class KdeConnectBatteryLowSensor(KdeConnectEntity, BinarySensorEntity):
    """A binary sensor checking if a KDE Connect device is low on battery."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_should_poll = False

    def __init__(
        self, device: KdeConnectDevice, plugin_registry: PluginRegistry
    ) -> None:
        """Initialize the battery low sensor."""
        super().__init__(device)
        self.battery_plugin = plugin_registry.get_plugin(device, BatteryReceiverPlugin)
        self.battery_plugin.register_low_changed_callback(self.on_battery_update)

        self._attr_name = f"{device.device_name} Battery Low"
        self._attr_unique_id = f"{device.device_id}/battery_low"

    def __del__(self) -> None:
        """Clean up callbacks on destruction."""
        self.battery_plugin.unregister_low_changed_callback(self.on_battery_update)

    async def on_battery_update(self, low: bool) -> None:
        """Handle a battery update."""
        self._attr_is_on = low
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
