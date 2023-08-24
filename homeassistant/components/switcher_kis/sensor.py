"""Switcher integration Sensor platform."""
from __future__ import annotations

from dataclasses import dataclass

from aioswitcher.device import DeviceCategory

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SwitcherDataUpdateCoordinator
from .const import SIGNAL_DEVICE_ADD


@dataclass
class AttributeDescription:
    """Class to describe a sensor."""

    name: str
    icon: str | None = None
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    default_enabled: bool = True


POWER_SENSORS = {
    "power_consumption": AttributeDescription(
        name="Power Consumption",
        unit=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "electric_current": AttributeDescription(
        name="Electric Current",
        unit=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
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
    def async_add_sensors(coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Add sensors from Switcher device."""
        if coordinator.data.device_type.category == DeviceCategory.POWER_PLUG:
            async_add_entities(
                SwitcherSensorEntity(coordinator, attribute, info)
                for attribute, info in POWER_PLUG_SENSORS.items()
            )
        elif coordinator.data.device_type.category == DeviceCategory.WATER_HEATER:
            async_add_entities(
                SwitcherSensorEntity(coordinator, attribute, info)
                for attribute, info in WATER_HEATER_SENSORS.items()
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADD, async_add_sensors)
    )


class SwitcherSensorEntity(
    CoordinatorEntity[SwitcherDataUpdateCoordinator], SensorEntity
):
    """Representation of a Switcher sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SwitcherDataUpdateCoordinator,
        attribute: str,
        description: AttributeDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.attribute = attribute

        # Entity class attributes
        self._attr_icon = description.icon
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_entity_registry_enabled_default = description.default_enabled

        self._attr_unique_id = (
            f"{coordinator.device_id}-{coordinator.mac_address}-{attribute}"
        )
        self._attr_device_info = {
            "connections": {(dr.CONNECTION_NETWORK_MAC, coordinator.mac_address)}
        }

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return getattr(self.coordinator.data, self.attribute)  # type: ignore[no-any-return]
