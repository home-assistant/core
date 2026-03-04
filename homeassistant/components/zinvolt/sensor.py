"""Sensor platform for Zinvolt integration."""

from collections.abc import Callable
from dataclasses import dataclass

from zinvolt.models import BatteryState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ZinvoltConfigEntry, ZinvoltDeviceCoordinator
from .entity import ZinvoltEntity


@dataclass(kw_only=True, frozen=True)
class ZinvoltBatteryStateDescription(SensorEntityDescription):
    """Sensor description for Zinvolt battery state."""

    value_fn: Callable[[BatteryState], float]


SENSORS: tuple[ZinvoltBatteryStateDescription, ...] = (
    ZinvoltBatteryStateDescription(
        key="state_of_charge",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda state: state.current_power.state_of_charge,
    ),
    ZinvoltBatteryStateDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda state: 0 - state.current_power.power_socket_output,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZinvoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize the entries."""

    async_add_entities(
        ZinvoltBatteryStateSensor(coordinator, description)
        for description in SENSORS
        for coordinator in entry.runtime_data.values()
    )


class ZinvoltBatteryStateSensor(ZinvoltEntity, SensorEntity):
    """Zinvolt battery state sensor."""

    entity_description: ZinvoltBatteryStateDescription

    def __init__(
        self,
        coordinator: ZinvoltDeviceCoordinator,
        description: ZinvoltBatteryStateDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}.{description.key}"

    @property
    def native_value(self) -> float:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
