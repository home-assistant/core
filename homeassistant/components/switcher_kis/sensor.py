"""Switcher integration Sensor platform."""

from __future__ import annotations

from aioswitcher.device import DeviceCategory

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import SIGNAL_DEVICE_ADD
from .coordinator import SwitcherDataUpdateCoordinator
from .entity import SwitcherEntity

POWER_SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="electric_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]
TIME_SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
    ),
    SensorEntityDescription(
        key="auto_off_set",
        translation_key="auto_shutdown",
        entity_registry_enabled_default=False,
    ),
]

POWER_PLUG_SENSORS = POWER_SENSORS
WATER_HEATER_SENSORS = [*POWER_SENSORS, *TIME_SENSORS]


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
                SwitcherSensorEntity(coordinator, description)
                for description in POWER_PLUG_SENSORS
            )
        elif coordinator.data.device_type.category == DeviceCategory.WATER_HEATER:
            async_add_entities(
                SwitcherSensorEntity(coordinator, description)
                for description in WATER_HEATER_SENSORS
            )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_ADD, async_add_sensors)
    )


class SwitcherSensorEntity(SwitcherEntity, SensorEntity):
    """Representation of a Switcher sensor entity."""

    def __init__(
        self,
        coordinator: SwitcherDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = (
            f"{coordinator.device_id}-{coordinator.mac_address}-{description.key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return getattr(self.coordinator.data, self.entity_description.key)  # type: ignore[no-any-return]
