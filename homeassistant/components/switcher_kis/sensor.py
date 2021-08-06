"""Switcher integration Sensor platform."""
from __future__ import annotations

from dataclasses import dataclass

from aioswitcher.device import DeviceCategory

from homeassistant.components.sensor import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_POWER,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ELECTRIC_CURRENT_AMPERE, POWER_WATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SwitcherDeviceWrapper
from .const import SIGNAL_DEVICE_ADD


@dataclass
class AttributeDescription:
    """Class to describe a sensor."""

    name: str
    icon: str | None = None
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    default_enabled: bool = True


POWER_SENSORS = {
    "power_consumption": AttributeDescription(
        name="Power Consumption",
        unit=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    "electric_current": AttributeDescription(
        name="Electric Current",
        unit=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
}

TIME_SENSORS = {
    "remaining_time": AttributeDescription(
        name="Remaining Time",
        icon="mdi:av-timer",
    ),
    "auto_off_set": AttributeDescription(
        name="Auto Shutdown",
        icon="mdi:progress-clock",
        default_enabled=False,
    ),
}

POWER_PLUG_SENSORS = POWER_SENSORS
WATER_HEATER_SENSORS = {**POWER_SENSORS, **TIME_SENSORS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Switcher sensor from config entry."""

    @callback
    def async_add_sensors(wrapper: SwitcherDeviceWrapper) -> None:
        """Add sensors from Switcher device."""
        if wrapper.data.device_type.category == DeviceCategory.POWER_PLUG:
            async_add_entities(
                SwitcherSensorEntity(wrapper, attribute, info)
                for attribute, info in POWER_PLUG_SENSORS.items()
            )
        elif wrapper.data.device_type.category == DeviceCategory.WATER_HEATER:
            async_add_entities(
                SwitcherSensorEntity(wrapper, attribute, info)
                for attribute, info in WATER_HEATER_SENSORS.items()
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADD, async_add_sensors)
    )


class SwitcherSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of a Switcher sensor entity."""

    def __init__(
        self,
        wrapper: SwitcherDeviceWrapper,
        attribute: str,
        description: AttributeDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(wrapper)
        self.wrapper = wrapper
        self.attribute = attribute

        # Entity class attributes
        self._attr_name = f"{wrapper.name} {description.name}"
        self._attr_icon = description.icon
        self._attr_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_entity_registry_enabled_default = description.default_enabled

        self._attr_unique_id = f"{wrapper.device_id}-{wrapper.mac_address}-{attribute}"
        self._attr_device_info = {
            "connections": {
                (device_registry.CONNECTION_NETWORK_MAC, wrapper.mac_address)
            }
        }

    @property
    def state(self) -> StateType:
        """Return value of sensor."""
        return getattr(self.wrapper.data, self.attribute)  # type: ignore[no-any-return]
