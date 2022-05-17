"""Support for Alpha2 base and IO device sensors."""
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Alpha2BaseCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Alpha2 sensor entities from a config_entry."""

    coordinator: Alpha2BaseCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Alpha2IODeviceBatterySensor(coordinator, io_device_id)
        for io_device_id in coordinator.data["io_devices"]
    )
    # HEATCTRL atrribute ACTOR_PERCENT is not available in older firmware versions
    async_add_entities(
        Alpha2HeatControlValveOpeningSensor(coordinator, heat_control_id)
        for heat_control_id, heat_control in coordinator.data["heat_controls"].items()
        if heat_control["INUSE"] and heat_control.get("ACTOR_PERCENT") is not None
    )


class Alpha2IODeviceBatterySensor(CoordinatorEntity, SensorEntity):
    """Alpha2 IO device battery sensor."""

    coordinator: Alpha2BaseCoordinator

    device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: Alpha2BaseCoordinator, io_device_id: str) -> None:
        """Initialize Alpha2IODeviceBatterySensor."""
        super().__init__(coordinator)
        self.io_device_id = io_device_id
        self._attr_unique_id = f"{io_device_id}:battery"

    @property
    def name(self) -> str:
        """Return the name of the battery sensor."""
        return f"Alpha2 IO device {self.io_device_id} battery"

    @property
    def native_value(self) -> int:
        """Return the current battery level percentage."""
        battery = self.coordinator.data["io_devices"][self.io_device_id]["BATTERY"]
        # 0=empty, 1=weak, 2=good
        if battery == 0:
            return 0
        if battery == 1:
            return 20
        return 100


class Alpha2HeatControlValveOpeningSensor(CoordinatorEntity, SensorEntity):
    """Alpha2 heat control valve opening sensor."""

    coordinator: Alpha2BaseCoordinator

    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: Alpha2BaseCoordinator, heat_control_id: str
    ) -> None:
        """Initialize Alpha2HeatControlValveOpeningSensor."""
        super().__init__(coordinator)
        self.heat_control_id = heat_control_id
        self._attr_unique_id = f"{heat_control_id}:valve_opening"

    @property
    def name(self) -> str:
        """Return the name of the valve sensor."""
        return f"Alpha2 heat control {self.heat_control_id} valve opening"

    @property
    def native_value(self) -> int:
        """Return the current valve opening percentage."""
        return self.coordinator.data["heat_controls"][self.heat_control_id][
            "ACTOR_PERCENT"
        ]
