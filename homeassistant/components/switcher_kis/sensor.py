"""Switcher integration Sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from aioswitcher.device import (
    DeviceCategory,
    SwitcherBase,
    SwitcherPowerBase,
    SwitcherThermostatBase,
    SwitcherTimedBase,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import SIGNAL_DEVICE_ADD
from .coordinator import SwitcherDataUpdateCoordinator
from .entity import SwitcherEntity


@dataclass(frozen=True, kw_only=True)
class SwitcherSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Switcher sensor entity."""

    value_fn: Callable[[SwitcherBase], StateType]


POWER_SENSORS: list[SwitcherSensorEntityDescription] = [
    SwitcherSensorEntityDescription(
        key="power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(SwitcherPowerBase, data).power_consumption,
    ),
    SwitcherSensorEntityDescription(
        key="electric_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(SwitcherPowerBase, data).electric_current,
    ),
]
TIME_SENSORS: list[SwitcherSensorEntityDescription] = [
    SwitcherSensorEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
        value_fn=lambda data: cast(SwitcherTimedBase, data).remaining_time,
    ),
    SwitcherSensorEntityDescription(
        key="auto_off_set",
        translation_key="auto_shutdown",
        entity_registry_enabled_default=False,
        value_fn=lambda data: cast(SwitcherTimedBase, data).auto_shutdown,
    ),
]
TEMPERATURE_SENSORS: list[SwitcherSensorEntityDescription] = [
    SwitcherSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        value_fn=lambda data: cast(SwitcherThermostatBase, data).temperature,
    ),
]

POWER_PLUG_SENSORS = POWER_SENSORS
WATER_HEATER_SENSORS = [*POWER_SENSORS, *TIME_SENSORS]
THERMOSTAT_SENSORS = TEMPERATURE_SENSORS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switcher sensor from config entry."""

    @callback
    def async_add_sensors(coordinator: SwitcherDataUpdateCoordinator) -> None:
        """Add sensors from Switcher device."""
        if coordinator.data.device_type.category == DeviceCategory.POWER_PLUG:
            async_add_entities(
                SwitcherSensorEntity(coordinator, description)
                for description in POWER_PLUG_SENSORS
            )
        elif coordinator.data.device_type.category == DeviceCategory.WATER_HEATER:
            async_add_entities(
                SwitcherSensorEntity(coordinator, description)
                for description in WATER_HEATER_SENSORS
            )
        elif coordinator.data.device_type.category == DeviceCategory.THERMOSTAT:
            async_add_entities(
                SwitcherSensorEntity(coordinator, description)
                for description in THERMOSTAT_SENSORS
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADD, async_add_sensors)
    )


class SwitcherSensorEntity(SwitcherEntity, SensorEntity):
    """Representation of a Switcher sensor entity."""

    def __init__(
        self,
        coordinator: SwitcherDataUpdateCoordinator,
        description: SwitcherSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description: SwitcherSensorEntityDescription = description

        self._attr_unique_id = (
            f"{coordinator.device_id}-{coordinator.mac_address}-{description.key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
