"""Support for KDE Connect sensors."""
from typing import cast

from pykdeconnect.client import KdeConnectClient
from pykdeconnect.devices import KdeConnectDevice
from pykdeconnect.plugin_registry import PluginRegistry
from pykdeconnect.plugins.battery import BatteryReceiverPlugin

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KdeConnectEntity
from .const import DATA_KEY_CLIENT, DATA_KEY_DEVICES, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the KDE Connect sensors."""
    client = cast(KdeConnectClient, hass.data[DOMAIN][DATA_KEY_CLIENT])
    device = cast(KdeConnectDevice, hass.data[DOMAIN][DATA_KEY_DEVICES][entry.entry_id])

    async_add_entities([KdeConnectBatteryChargeSensor(device, client.plugin_registry)])


class KdeConnectBatteryChargeSensor(KdeConnectEntity, SensorEntity):
    """A sensor reading the battery charge from a KDE Connect device."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"
    _attr_should_poll = False

    def __init__(
        self, device: KdeConnectDevice, plugin_registry: PluginRegistry
    ) -> None:
        """Initialize the battery charge sensor."""
        super().__init__(device)
        self.current_charge = None
        self.battery_plugin = plugin_registry.get_plugin(device, BatteryReceiverPlugin)
        self.battery_plugin.register_charge_changed_callback(self.on_battery_update)

        self._attr_name = f"{device.device_name} Battery Charge"
        self._attr_unique_id = f"{device.device_id}/battery_charge"

    def __del__(self) -> None:
        """Clean up callbacks on destruction."""
        self.battery_plugin.unregister_charge_changed_callback(self.on_battery_update)

    async def on_battery_update(self, charge: int) -> None:
        """Handle a battery update."""
        self._attr_native_value = charge
        self.async_schedule_update_ha_state()

    def restore_state(self, state: State) -> None:
        """Restore the state of the device on restart."""
        if state.state != STATE_UNKNOWN:
            self._attr_native_value = int(state.state)
