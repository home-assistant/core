"""Support for KDE Connect sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

from pykdeconnect.client import KdeConnectClient
from pykdeconnect.devices import KdeConnectDevice
from pykdeconnect.plugin import Plugin
from pykdeconnect.plugin_registry import PluginRegistry
from pykdeconnect.plugins.battery import BatteryReceiverPlugin

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import KdeConnectPluginEntity
from .const import DATA_KEY_CLIENT, DATA_KEY_DEVICES, DOMAIN
from .helpers import is_plugin_compatible, raise_typeerror


@dataclass
class KdeConnectSensorEntityDescription(SensorEntityDescription):
    """Describes a KDE Connect binary sensor."""

    # KDE Connect plugin to load
    plugin_type: type[Plugin] = field(
        default_factory=raise_typeerror("Missing positional argument plugin_type")
    )

    # Function converting string back to state.
    sensor_restore_type: Callable[[str], StateType] = str


SENSOR_TYPES = [
    KdeConnectSensorEntityDescription(
        key="battery_charge",
        name="Battery Charge",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.BATTERY,
        plugin_type=BatteryReceiverPlugin,
        sensor_restore_type=int,
    )
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the KDE Connect sensors."""
    client = cast(KdeConnectClient, hass.data[DOMAIN][DATA_KEY_CLIENT])
    device = cast(KdeConnectDevice, hass.data[DOMAIN][DATA_KEY_DEVICES][entry.entry_id])
    plugin_registry = client.plugin_registry

    entities = [
        KdeConnectSensor(device, plugin_registry, description)
        for description in SENSOR_TYPES
        if is_plugin_compatible(plugin_registry, device, description.plugin_type)
    ]

    async_add_entities(entities)


class KdeConnectSensor(KdeConnectPluginEntity, SensorEntity):
    """A sensor reading the battery charge from a KDE Connect device."""

    _attr_should_poll = False

    def __init__(
        self,
        device: KdeConnectDevice,
        plugin_registry: PluginRegistry,
        description: KdeConnectSensorEntityDescription,
    ) -> None:
        """Initialize the battery charge sensor."""
        super().__init__(device, plugin_registry, description.plugin_type)
        self.entity_description = description
        self.restore_type = description.sensor_restore_type
        self._attr_name = f"{device.device_name} {description.name}"
        self._attr_unique_id = f"{device.device_id}/{description.key}"

        if description.key == "battery_charge":
            self.plugin.register_charge_changed_callback(self.on_value_changed)
        else:
            assert False  # pragma: no cover

    def __del__(self) -> None:
        """Clean up callbacks on destruction."""
        if self.entity_description.key == "battery_charge":
            self.plugin.unregister_charge_changed_callback(self.on_value_changed)
        else:
            assert False  # pragma: no cover

    async def on_value_changed(self, value: Any) -> None:
        """Handle a sensor update."""
        self._attr_native_value = value
        self.async_schedule_update_ha_state()

    def restore_state(self, state: State) -> None:
        """Restore the state of the device on restart."""
        if state.state != STATE_UNKNOWN:
            self._attr_native_value = self.restore_type(state.state)
